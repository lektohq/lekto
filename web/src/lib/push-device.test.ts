import { afterEach, describe, expect, it, vi } from 'vitest';
import { deviceName, keyBytes } from '#lib/push-device.ts';

function agent(value: string, touchPoints = 0) {
	vi.spyOn(navigator, 'userAgent', 'get').mockReturnValue(value);
	Object.defineProperty(navigator, 'maxTouchPoints', { value: touchPoints, configurable: true });
}

describe('this device', () => {
	afterEach(() => vi.restoreAllMocks());

	it('turns the server key into bytes', () => {
		expect([...keyBytes('BAEC_w')]).toEqual([4, 1, 2, 255]);
	});

	it('names the device by what it is and the browser', () => {
		agent('Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15', 5);
		expect(deviceName()).toBe('iPhone');
		agent(
			'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/18.0 Safari/605.1.15'
		);
		expect(deviceName()).toBe('Mac · Safari');
		agent(
			'Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 Chrome/140.0 Mobile Safari/537.36',
			5
		);
		expect(deviceName()).toBe('Android · Chrome');
		agent(
			'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0 Safari/537.36 Edg/140.0'
		);
		expect(deviceName()).toBe('Windows · Edge');
	});
});
