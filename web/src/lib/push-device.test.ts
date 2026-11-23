import { afterEach, describe, expect, it, vi } from 'vitest';
import {
	closeWaiting,
	deviceName,
	endForeignSubscription,
	currentSubscription,
	keyBytes,
	leaveDevice,
	notificationsBlocked,
	subscribe,
	unblockSteps,
	watchPermission
} from '#lib/push-device.ts';
import { calls, fakeApi, noContent, problem } from '#lib/testing/api.ts';
import { deviceOf as agent } from '#lib/testing/browser.ts';

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

	it('says where to allow notifications again in this browser', () => {
		vi.spyOn(window, 'matchMedia').mockReturnValue({ matches: false } as MediaQueryList);
		agent(
			'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/18.0 Safari/605.1.15'
		);
		expect(unblockSteps()).toEqual(['safari', 'macos']);
		vi.spyOn(window, 'matchMedia').mockReturnValue({ matches: true } as MediaQueryList);
		expect(unblockSteps()).toEqual(['dock-app', 'macos']);
		agent(
			'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/140.0 Safari/537.36'
		);
		expect(unblockSteps()).toEqual(['address-bar']);
	});

	it('names the settings of a phone, not a Mac’s menu bar or a click (WM-03)', () => {
		const standalone = (matches: boolean) =>
			vi.spyOn(window, 'matchMedia').mockReturnValue({ matches } as MediaQueryList);
		// The installed app on an iPhone and an iPad (their web apps send no "Safari/").
		standalone(true);
		agent(
			'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148'
		);
		expect(unblockSteps()).toEqual(['ios-app']);
		agent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Mobile/15E148', 5);
		expect(unblockSteps()).toEqual(['ios-app']);
		// Android: the installed app has no address bar; the browser's is tapped.
		const android =
			'Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 Chrome/140.0 Mobile Safari/537.36';
		agent(android);
		expect(unblockSteps()).toEqual(['android-app']);
		standalone(false);
		expect(unblockSteps()).toEqual(['address-bar-tap']);
	});

	it('reads the permission again when the person comes back from the settings', () => {
		vi.stubGlobal('Notification', { permission: 'denied' });
		expect(notificationsBlocked()).toBe(true);
		const changed = vi.fn();
		const stop = watchPermission(changed);
		window.dispatchEvent(new Event('focus'));
		document.dispatchEvent(new Event('visibilitychange'));
		expect(changed).toHaveBeenCalledTimes(2);
		vi.stubGlobal('Notification', { permission: 'granted' });
		expect(notificationsBlocked()).toBe(false);
		stop();
		window.dispatchEvent(new Event('focus'));
		expect(changed).toHaveBeenCalledTimes(2);
	});
});

const ENDPOINT = 'https://push.example/own';
const device = (id: string, endpoint: string) => ({ id, name: 'Mac · Safari', endpoint });

/** A service worker of this browser with a push subscription (or none) and shown notifications. */
function browserWith(endpoint: string | null, shown = 0) {
	const subscription = endpoint
		? { endpoint, unsubscribe: vi.fn<() => Promise<boolean>>(async () => true) }
		: null;
	const notifications = Array.from({ length: shown }, () => ({ close: vi.fn() }));
	const registration = {
		pushManager: { getSubscription: async () => subscription },
		getNotifications: async () => notifications
	};
	vi.stubGlobal('navigator', {
		userAgent: 'test',
		serviceWorker: { getRegistration: async () => registration },
		clearAppBadge: vi.fn(async () => {}),
		setAppBadge: vi.fn(async () => {})
	});
	return { subscription, notifications };
}

const clearedBadge = () =>
	vi.mocked((navigator as Navigator & { clearAppBadge: () => Promise<void> }).clearAppBadge);

describe('a subscription of an earlier server key (WH-05)', () => {
	// Two keys of the server, as bytes and as the base64url text the API gives.
	const OLD = 'AQID';
	const NEW = 'BAUG';

	/** A browser that holds a subscription made with `key` and refuses a second with another. */
	function browserSubscribed(key: string) {
		const held = {
			endpoint: ENDPOINT,
			options: { applicationServerKey: keyBytes(key).buffer },
			unsubscribe: vi.fn<() => Promise<boolean>>(async () => true)
		};
		let current: typeof held | null = held;
		held.unsubscribe.mockImplementation(async () => {
			current = null;
			return true;
		});
		const made = { endpoint: 'https://push.example/new' };
		const subscribing = vi.fn(async () => {
			if (current) throw new DOMException('another key', 'InvalidStateError');
			return made;
		});
		vi.stubGlobal('Notification', { requestPermission: async () => 'granted' });
		vi.stubGlobal('navigator', {
			userAgent: 'test',
			serviceWorker: {
				getRegistration: async () => ({
					pushManager: { getSubscription: async () => current, subscribe: subscribing }
				})
			}
		});
		return { held, made, subscribing };
	}

	it('ends it and has the server forget its device before subscribing anew', async () => {
		const { held, made } = browserSubscribed(OLD);
		const api = fakeApi({
			'GET /api/v1/push/devices': () => [device('d-own', ENDPOINT)],
			'DELETE /api/v1/push/devices/d-own': () => noContent()
		});
		vi.stubGlobal('fetch', api);
		expect(await subscribe(NEW)).toBe(made);
		expect(held.unsubscribe).toHaveBeenCalledOnce();
		expect(calls(api)).toContain('DELETE /api/v1/push/devices/d-own');
	});

	it('keeps a subscription made with the key the server has', async () => {
		const { held, subscribing } = browserSubscribed(NEW);
		vi.stubGlobal('fetch', fakeApi());
		await expect(subscribe(NEW)).rejects.toThrow();
		expect(held.unsubscribe).not.toHaveBeenCalled();
		expect(subscribing).toHaveBeenCalledOnce();
	});

	it('counts the device as off while its subscription is of another key', async () => {
		browserSubscribed(OLD);
		expect(await currentSubscription(NEW)).toBeNull();
		expect((await currentSubscription(OLD))?.endpoint).toBe(ENDPOINT);
		// Without a key to compare with, the subscription as it is.
		expect((await currentSubscription())?.endpoint).toBe(ENDPOINT);
	});
});

describe('the notification of what waits, once nothing waits (WM-05)', () => {
	it('is closed by the open app, and only that one', async () => {
		const asked: unknown[] = [];
		const waiting = [{ close: vi.fn() }];
		vi.stubGlobal('navigator', {
			userAgent: 'test',
			serviceWorker: {
				getRegistration: async () => ({
					getNotifications: async (filter: unknown) => {
						asked.push(filter);
						return waiting;
					}
				})
			}
		});
		await closeWaiting();
		expect(asked).toEqual([{ tag: 'lekto-waiting' }]);
		expect(waiting[0].close).toHaveBeenCalledOnce();
	});

	it('does nothing in a browser without a service worker', async () => {
		vi.stubGlobal('navigator', { userAgent: 'test' });
		await expect(closeWaiting()).resolves.toBeUndefined();
	});
});

describe('giving this device up on signing out', () => {
	afterEach(() => {
		vi.useRealTimers();
	});

	it('removes the device at the server, ends the subscription, closes what is shown', async () => {
		const { subscription, notifications } = browserWith(ENDPOINT, 2);
		const api = fakeApi({
			'GET /api/v1/push/devices': () => [
				device('d-other', 'https://push.example/phone'),
				device('d-own', ENDPOINT)
			],
			'DELETE /api/v1/push/devices/d-own': () => noContent()
		});
		vi.stubGlobal('fetch', api);

		await leaveDevice();

		// Only this browser's device, not the person's other ones.
		expect(calls(api).filter((call) => call.startsWith('DELETE'))).toEqual([
			'DELETE /api/v1/push/devices/d-own'
		]);
		expect(subscription!.unsubscribe).toHaveBeenCalledTimes(1);
		for (const notification of notifications) expect(notification.close).toHaveBeenCalled();
		expect(clearedBadge()).toHaveBeenCalled();
	});

	it('ends the subscription even when the server cannot be told', async () => {
		const { subscription } = browserWith(ENDPOINT, 1);
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => {
				throw new TypeError('Failed to fetch');
			})
		);

		await expect(leaveDevice()).resolves.toBeUndefined();

		expect(subscription!.unsubscribe).toHaveBeenCalledTimes(1);
		expect(clearedBadge()).toHaveBeenCalled();
	});

	it('asks the server nothing without a subscription, and still clears what is shown', async () => {
		const { notifications } = browserWith(null, 1);
		const api = fakeApi();
		vi.stubGlobal('fetch', api);

		await leaveDevice();

		expect(calls(api)).toEqual([]);
		expect(notifications[0].close).toHaveBeenCalled();
		expect(clearedBadge()).toHaveBeenCalled();
	});

	it('does not hold signing out up when the push service does not answer', async () => {
		vi.useFakeTimers();
		const { subscription } = browserWith(ENDPOINT);
		subscription!.unsubscribe.mockReturnValue(new Promise(() => {}));
		vi.stubGlobal('fetch', fakeApi({ 'GET /api/v1/push/devices': () => [] }));

		let left = false;
		const leaving = leaveDevice().then(() => (left = true));
		await vi.advanceTimersByTimeAsync(2999);
		expect(left).toBe(false);
		await vi.advanceTimersByTimeAsync(1);
		await leaving;
		expect(left).toBe(true);
	});

	it('works in a browser without a service worker', async () => {
		vi.stubGlobal('navigator', { userAgent: 'test' });
		await expect(leaveDevice()).resolves.toBeUndefined();
	});
});

describe('a subscription this browser still has from someone else', () => {
	it("ends when it is none of the signed-in user's devices", async () => {
		const { subscription, notifications } = browserWith(ENDPOINT, 1);
		const api = fakeApi({
			'GET /api/v1/push/devices': () => [device('d-phone', 'https://push.example/phone')]
		});
		vi.stubGlobal('fetch', api);

		await endForeignSubscription();

		expect(subscription!.unsubscribe).toHaveBeenCalledTimes(1);
		expect(notifications[0].close).toHaveBeenCalled();
		// The device is another user's: nothing to delete for this one.
		expect(calls(api)).toEqual(['GET /api/v1/push/devices']);
	});

	it("stays when it is one of the user's own devices", async () => {
		const { subscription, notifications } = browserWith(ENDPOINT, 1);
		vi.stubGlobal(
			'fetch',
			fakeApi({ 'GET /api/v1/push/devices': () => [device('d-own', ENDPOINT)] })
		);

		await endForeignSubscription();

		expect(subscription!.unsubscribe).not.toHaveBeenCalled();
		expect(notifications[0].close).not.toHaveBeenCalled();
	});

	it('stays while the API does not say whose it is', async () => {
		const { subscription } = browserWith(ENDPOINT);
		vi.stubGlobal(
			'fetch',
			fakeApi({
				'GET /api/v1/push/devices': () => problem(503)
			})
		);

		await expect(endForeignSubscription()).resolves.toBeUndefined();

		expect(subscription!.unsubscribe).not.toHaveBeenCalled();
	});

	it('asks the API nothing in a browser without a subscription', async () => {
		browserWith(null);
		const api = fakeApi();
		vi.stubGlobal('fetch', api);

		await endForeignSubscription();

		expect(calls(api)).toEqual([]);
	});
});
