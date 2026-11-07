import { toast } from 'svelte-sonner';
import { dev, version } from '$app/env';
import { BASE } from '#lib/base.ts';
import { m } from '#lib/paraglide/messages.js';

// The service worker (`src/service-worker/index.ts`) and the way to a new version (web/DESIGN.md,
// "App"): a new worker waits until the person taps "Neu laden" in a toast that stays; the X puts
// it off until the app starts the next time.

/** How often a running app asks whether there is a new version, besides when it comes back to
 * the front. */
const CHECK_EVERY = 30 * 60 * 1000;
const TOAST = 'app-update';

let reloadAsked = false;

/** Register the service worker and watch for new versions; nothing during `pnpm dev`. */
export function startAppUpdates(): void {
	if (dev || !('serviceWorker' in navigator)) return;
	const container = navigator.serviceWorker;
	container.addEventListener('controllerchange', () => {
		if (reloadAsked) window.location.reload();
	});
	container.register(`${BASE}/service-worker.js`, { scope: `${BASE}/` }).then(
		(registration) => {
			watch(registration);
			// What the page loaded before the worker was in control is kept, too.
			void container.ready.then((ready) =>
				ready.active?.postMessage({
					type: 'keep',
					urls: performance.getEntriesByType('resource').map((entry) => entry.name)
				})
			);
		},
		() => {
			// No service worker (plain HTTP, a private window): the app works without one.
		}
	);
}

function watch(registration: ServiceWorkerRegistration): void {
	void offer(registration);
	registration.addEventListener('updatefound', () => {
		const installing = registration.installing;
		installing?.addEventListener('statechange', () => {
			if (installing.state === 'installed') void offer(registration);
		});
	});
	const check = () => void registration.update().catch(() => undefined);
	document.addEventListener('visibilitychange', () => {
		if (document.visibilityState === 'visible') check();
	});
	setInterval(check, CHECK_EVERY);
}

/** Offer the waiting version, unless this page already runs it (a reload fetched the newest
 * page): then the worker takes over without a word. */
async function offer(registration: ServiceWorkerRegistration): Promise<void> {
	const waiting = registration.waiting;
	if (!waiting || !navigator.serviceWorker.controller) return;
	if ((await versionOf(waiting)) === version) {
		waiting.postMessage({ type: 'skip-waiting' });
		return;
	}
	toast(m.app_update_title(), {
		id: TOAST,
		duration: Number.POSITIVE_INFINITY,
		action: {
			label: m.app_update_reload(),
			onClick: () => {
				reloadAsked = true;
				const next = registration.waiting;
				if (next) next.postMessage({ type: 'skip-waiting' });
				else window.location.reload();
			}
		}
	});
}

function versionOf(worker: ServiceWorker): Promise<string | null> {
	return new Promise((resolve) => {
		const channel = new MessageChannel();
		const timer = setTimeout(() => resolve(null), 1000);
		channel.port1.onmessage = (event: MessageEvent<{ version?: string }>) => {
			clearTimeout(timer);
			resolve(event.data.version ?? null);
		};
		worker.postMessage({ type: 'version' }, [channel.port2]);
	});
}
