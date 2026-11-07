import { afterEach, describe, expect, it, vi } from 'vitest';
import { appleDevice, isAndroid } from '#lib/install.svelte.ts';

function device(agent: string, touchPoints = 0) {
	vi.spyOn(navigator, 'userAgent', 'get').mockReturnValue(agent);
	// jsdom has no touch points: set them for the test.
	Object.defineProperty(navigator, 'maxTouchPoints', { value: touchPoints, configurable: true });
}

describe('the device', () => {
	afterEach(() => vi.restoreAllMocks());

	it('tells iPhone, iPad and Mac apart, an iPad that names itself a Mac by its touch screen', () => {
		device('Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15', 5);
		expect(appleDevice()).toBe('iPhone');
		device('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15', 5);
		expect(appleDevice()).toBe('iPad');
		device('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15', 0);
		expect(appleDevice()).toBe('Mac');
	});

	it('finds Android, and no Apple device there', () => {
		device('Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 Chrome/140.0', 5);
		expect(isAndroid()).toBe(true);
		expect(appleDevice()).toBeNull();
	});
});
