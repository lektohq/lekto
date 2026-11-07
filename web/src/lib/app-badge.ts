/**
 * The number on the installed app's icon (web/DESIGN.md, "App"): everything open in the inbox,
 * as its counter in the menu says. A notification sets it while the app is closed; the open app
 * keeps it with the counter. Browsers without badges ignore it.
 */
export function setAppBadge(open: number | null | undefined): void {
	const navigator = window.navigator as Navigator & {
		setAppBadge?: (count?: number) => Promise<void>;
		clearAppBadge?: () => Promise<void>;
	};
	const done = open ? navigator.setAppBadge?.(open) : navigator.clearAppBadge?.();
	void done?.catch(() => undefined);
}
