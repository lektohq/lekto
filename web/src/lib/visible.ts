/**
 * Something a tab holds only while it is looked at. Each tab of Lekto holds a connection for
 * its events, and over HTTP/1.1 a browser opens at most six to a host: with six tabs open no
 * request of any tab got an answer any more. A hidden tab shows nothing, so it lets go of
 * what it holds and takes it up again when it is shown.
 */

/** How long a tab is hidden before it lets go: switching to another tab and back is none. */
export const HIDDEN_GRACE_MS = 5_000;

/**
 * Call `open` now if the tab shows, and whenever it shows again after `close` was called;
 * call `close` once the tab was hidden for `grace`. Returns the function that ends the watch
 * (it calls neither).
 */
export function whileVisible(
	open: () => void,
	close: () => void,
	grace: number = HIDDEN_GRACE_MS
): () => void {
	let timer: ReturnType<typeof setTimeout> | undefined;
	let held = false;
	const take = () => {
		held = true;
		open();
	};
	const change = () => {
		clearTimeout(timer);
		if (document.visibilityState === 'hidden') {
			timer = setTimeout(() => {
				if (!held) return;
				held = false;
				close();
			}, grace);
		} else if (!held) {
			take();
		}
	};
	if (document.visibilityState !== 'hidden') take();
	document.addEventListener('visibilitychange', change);
	return () => {
		clearTimeout(timer);
		document.removeEventListener('visibilitychange', change);
	};
}
