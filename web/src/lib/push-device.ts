import { unwrap } from '#lib/api/call.ts';
import { api } from '#lib/api/client.ts';
import { setAppBadge } from '#lib/app-badge.ts';
import { BASE } from '#lib/base.ts';
import { appleDevice, isAndroid } from '#lib/install.svelte.ts';

/**
 * Notifications on this device (web/DESIGN.md, "App"): whether it can have them, its
 * subscription at its push service and a name for it. The server keeps the devices
 * (`/push/devices`); the service worker shows what comes (`src/service-worker/`).
 */

/** `ready`: the browser can subscribe; `install-first`: an iPhone or iPad in Safari, where only
 * the app on the Home Screen gets notifications; `unsupported`: no push in this browser. */
export type PushSupport = 'ready' | 'install-first' | 'unsupported';

/** Whether the app runs installed, on its own (not in a browser tab). */
export function installed(): boolean {
	const ios = (navigator as Navigator & { standalone?: boolean }).standalone === true;
	return ios || window.matchMedia('(display-mode: standalone)').matches;
}

export function pushSupport(): PushSupport {
	const apple = appleDevice();
	if ((apple === 'iPhone' || apple === 'iPad') && !installed()) return 'install-first';
	const capable =
		'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
	return capable ? 'ready' : 'unsupported';
}

async function registration(): Promise<ServiceWorkerRegistration | null> {
	if (!('serviceWorker' in navigator)) return null;
	return (await navigator.serviceWorker.getRegistration(`${BASE}/`)) ?? null;
}

/** This browser's subscription, if it has one. */
export async function currentSubscription(): Promise<PushSubscription | null> {
	const found = await registration();
	return found ? await found.pushManager.getSubscription() : null;
}

/** A base64url key as the bytes `applicationServerKey` takes. */
export function keyBytes(base64url: string): Uint8Array<ArrayBuffer> {
	const base64 = base64url.replace(/-/g, '+').replace(/_/g, '/');
	const raw = atob(base64 + '='.repeat((4 - (base64.length % 4)) % 4));
	return Uint8Array.from(raw, (char) => char.charCodeAt(0));
}

/** Ask the person (from a tap: browsers allow it only then) and subscribe; `denied` if they
 * said no or blocked it before, `unavailable` without a service worker (`pnpm dev`). */
export async function subscribe(
	publicKey: string
): Promise<PushSubscription | 'denied' | 'unavailable'> {
	if ((await Notification.requestPermission()) !== 'granted') return 'denied';
	const found = await registration();
	if (!found) return 'unavailable';
	return found.pushManager.subscribe({
		userVisibleOnly: true,
		applicationServerKey: keyBytes(publicKey)
	});
}

/** How long signing out waits for the device to be given up; the push service may not answer. */
const LEAVE_WITHIN_MS = 3000;

/** End this browser's subscription and close the notifications it still shows. */
async function silence(found: ServiceWorkerRegistration, subscription: PushSubscription | null) {
	await subscription?.unsubscribe().catch(() => false);
	const shown = await found.getNotifications().catch(() => []);
	for (const notification of shown) notification.close();
}

async function leave(): Promise<void> {
	const found = await registration();
	if (!found) return;
	const subscription = await found.pushManager.getSubscription();
	if (subscription) {
		// The server forgets the device; if it cannot be told, the ended subscription tells it
		// with the next message it tries to send.
		try {
			const devices = await unwrap(api.GET('/api/v1/push/devices'));
			const own = devices.find((device) => device.endpoint === subscription.endpoint);
			if (own) {
				await unwrap(api.DELETE('/api/v1/push/devices/{id}', { params: { path: { id: own.id } } }));
			}
		} catch {
			// Offline, or the session is gone already.
		}
	}
	await silence(found, subscription);
}

/**
 * Give this device up, before the person signs out (the session must still hold): it gets no
 * more notifications of theirs, shows none any more, and the app's icon loses its number. On a
 * device others use too, the next person would read the titles of this one's documents
 * otherwise. Never throws and never holds signing out up for long.
 */
export async function leaveDevice(): Promise<void> {
	let timer: ReturnType<typeof setTimeout> | undefined;
	const late = new Promise<void>((resolve) => (timer = setTimeout(resolve, LEAVE_WITHIN_MS)));
	try {
		await Promise.race([leave(), late]);
	} catch {
		// Signing out goes on.
	} finally {
		clearTimeout(timer);
		setAppBadge(null);
	}
}

/**
 * End a subscription of this browser that is none of the signed-in user's devices: someone else
 * switched notifications on here and never signed out (their session ran out), or the server
 * has forgotten the device. Called once the app starts for a user. Never throws; without an
 * answer of the API the subscription stays.
 */
export async function endForeignSubscription(): Promise<void> {
	try {
		const found = await registration();
		const subscription = await found?.pushManager.getSubscription();
		if (!found || !subscription) return;
		const devices = await unwrap(api.GET('/api/v1/push/devices'));
		if (devices.some((device) => device.endpoint === subscription.endpoint)) return;
		await silence(found, subscription);
	} catch {
		// Not now: the next start tries again.
	}
}

function browserName(agent: string): string {
	if (/Edg\//.test(agent)) return 'Edge';
	if (/Firefox\//.test(agent)) return 'Firefox';
	if (/Chrome\//.test(agent)) return 'Chrome';
	if (/Safari\//.test(agent)) return 'Safari';
	return 'Browser';
}

function systemName(agent: string): string {
	if (/Windows/.test(agent)) return 'Windows';
	if (/CrOS/.test(agent)) return 'ChromeOS';
	if (/Linux/.test(agent)) return 'Linux';
	return '';
}

/** What the device list calls this device: "iPhone", "Mac · Safari", "Android · Chrome". */
export function deviceName(): string {
	const agent = navigator.userAgent;
	const apple = appleDevice();
	if (apple === 'iPhone' || apple === 'iPad') return apple;
	const system = apple ?? (isAndroid() ? 'Android' : systemName(agent));
	return [system, browserName(agent)].filter(Boolean).join(' · ');
}

/** Where the person allows notifications again after blocking them, for this browser: the app
 * in the Dock has settings of its own, apart from Safari's; macOS asks once more for the app. */
export type UnblockStep = 'dock-app' | 'safari' | 'address-bar' | 'macos';

export function unblockSteps(): UnblockStep[] {
	const agent = navigator.userAgent;
	const browser = browserName(agent);
	const mac = appleDevice() === 'Mac';
	const steps: UnblockStep[] = [];
	if (browser === 'Safari') steps.push(installed() ? 'dock-app' : 'safari');
	else steps.push('address-bar');
	if (mac) steps.push('macos');
	return steps;
}
