/**
 * A tap on a notification opens what it is about in the app that is already open (web/DESIGN.md,
 * "App"). The service worker asks the window to go there, and the app moves through its router:
 * nothing loads anew, uploads go on, and unsaved changes ask as they do on every way out. Only
 * a window that does not answer is loaded at the address. Both sides live here; neither needs
 * the framework, so the worker can take its half.
 */

/** The message of the worker to a window. */
export const OPEN = 'open';

/** How long the worker waits for a window to say it goes there. */
const ANSWER_WITHIN_MS = 1000;

/** What of a window the worker uses to ask it. */
export interface Asked {
	postMessage(message: unknown, transfer: Transferable[]): void;
}

/**
 * The worker's half: ask `window` to go to `url`; whether it said it does. A window this
 * worker does not control, or an app that has not started, says nothing.
 */
export function askToOpen(
	window: Asked,
	url: string,
	within: number = ANSWER_WITHIN_MS
): Promise<boolean> {
	return new Promise((resolve) => {
		const channel = new MessageChannel();
		const timer = setTimeout(() => done(false), within);
		function done(taken: boolean) {
			clearTimeout(timer);
			channel.port1.close();
			resolve(taken);
		}
		channel.port1.onmessage = () => done(true);
		try {
			window.postMessage({ type: OPEN, url }, [channel.port2]);
		} catch {
			done(false);
		}
	});
}

/** The path inside the app that `url` names; null for an address elsewhere. */
export function pathToOpen(url: unknown, origin: string, base: string): string | null {
	if (typeof url !== 'string') return null;
	try {
		const target = new URL(url, origin);
		const inside = target.pathname === base || target.pathname.startsWith(`${base}/`);
		return target.origin === origin && inside
			? `${target.pathname}${target.search}${target.hash}`
			: null;
	} catch {
		return null;
	}
}

/**
 * The app's half: hear the worker ask, answer, and go there with `go` (the router's `goto`).
 * Returns what ends the listening; does nothing in a browser without service workers.
 */
export function answerOpen(base: string, go: (path: string) => unknown): () => void {
	if (!('serviceWorker' in navigator)) return () => {};
	const container = navigator.serviceWorker;
	const heard = (event: MessageEvent) => {
		const data = event.data as { type?: unknown; url?: unknown } | null;
		if (data?.type !== OPEN) return;
		const path = pathToOpen(data.url, location.origin, base);
		if (path === null) return;
		event.ports[0]?.postMessage({ taken: true });
		void go(path);
	};
	container.addEventListener('message', heard);
	return () => container.removeEventListener('message', heard);
}
