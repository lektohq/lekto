import { describe, expect, it } from 'vitest';
import { install } from '#lib/install.svelte.ts';

describe('installing the app', () => {
	it('hears the browser’s offer from the start, before any page asks (WM-K06)', () => {
		const offer = Object.assign(new Event('beforeinstallprompt', { cancelable: true }), {
			prompt: async () => {},
			userChoice: Promise.resolve({ outcome: 'dismissed' as const })
		});
		window.dispatchEvent(offer);
		expect(offer.defaultPrevented).toBe(true);
		expect(install.available).toBe(true);
		window.dispatchEvent(new Event('appinstalled'));
		expect(install.available).toBe(false);
	});
});
