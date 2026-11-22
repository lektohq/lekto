/** Stand-ins for what a browser differs in, each given back once the test finished. */
import { onTestFinished, vi } from 'vitest';

/** `run` without storage, as in a private window or with blocked site data: reading
 * `localStorage` throws. */
export function withoutStorage(run: () => void): void {
	const storage = Object.getOwnPropertyDescriptor(globalThis, 'localStorage')!;
	Object.defineProperty(globalThis, 'localStorage', {
		configurable: true,
		get() {
			throw new Error('blocked');
		}
	});
	try {
		run();
	} finally {
		Object.defineProperty(globalThis, 'localStorage', storage);
	}
}

/** The browser of a device: its user agent and its touch points (jsdom has none). */
export function deviceOf(agent: string, touchPoints = 0): void {
	vi.spyOn(navigator, 'userAgent', 'get').mockReturnValue(agent);
	const before = Object.getOwnPropertyDescriptor(navigator, 'maxTouchPoints');
	Object.defineProperty(navigator, 'maxTouchPoints', { value: touchPoints, configurable: true });
	onTestFinished(() => {
		if (before) Object.defineProperty(navigator, 'maxTouchPoints', before);
		else Reflect.deleteProperty(navigator, 'maxTouchPoints');
	});
}
