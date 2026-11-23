// A tap on a notification moves the open app through its router (WM-04).
import { afterEach, describe, expect, it, vi } from 'vitest';
import { answerOpen, askToOpen, OPEN, pathToOpen } from './app-open.ts';

/** A service worker container that hands messages to its listeners, as the browser's does. */
function container() {
	const heard = new Set<(event: MessageEvent) => void>();
	const fake = {
		addEventListener: (_: string, listener: (event: MessageEvent) => void) => heard.add(listener),
		removeEventListener: (_: string, listener: (event: MessageEvent) => void) =>
			heard.delete(listener)
	};
	vi.stubGlobal('navigator', { serviceWorker: fake });
	const send = (data: unknown, port?: MessagePort) => {
		for (const listener of heard)
			listener({ data, ports: port ? [port] : [] } as unknown as MessageEvent);
	};
	return { send, listeners: heard };
}

afterEach(() => vi.useRealTimers());

describe('the address a window may be asked to open', () => {
	it('is a path of the app on this origin, with its query and hash', () => {
		const origin = 'https://lekto.example';
		expect(pathToOpen(`${origin}/ui/documents/12345?tab=processing#top`, origin, '/ui')).toBe(
			'/ui/documents/12345?tab=processing#top'
		);
		expect(pathToOpen('/ui/inbox', origin, '/ui')).toBe('/ui/inbox');
		expect(pathToOpen('https://elsewhere.example/ui/inbox', origin, '/ui')).toBeNull();
		expect(pathToOpen(`${origin}/api/v1/documents`, origin, '/ui')).toBeNull();
		expect(pathToOpen(`${origin}/uix`, origin, '/ui')).toBeNull();
		expect(pathToOpen(12345, origin, '/ui')).toBeNull();
	});
});

describe('the app, asked by the worker', () => {
	it('goes there through its router and says so', async () => {
		const { send } = container();
		const go = vi.fn();
		answerOpen('/ui', go);
		const channel = new MessageChannel();
		const answered = new Promise((resolve) => (channel.port1.onmessage = resolve));
		send({ type: OPEN, url: `${location.origin}/ui/inbox` }, channel.port2);
		expect(go).toHaveBeenCalledExactlyOnceWith('/ui/inbox');
		await answered;
		channel.port1.close();
	});

	it('neither answers nor moves for another message or an address elsewhere', () => {
		const { send } = container();
		const go = vi.fn();
		answerOpen('/ui', go);
		const port = { postMessage: vi.fn() } as unknown as MessagePort;
		send({ type: 'keep', urls: [] }, port);
		send({ type: OPEN, url: 'https://elsewhere.example/ui/inbox' }, port);
		expect(go).not.toHaveBeenCalled();
		expect(port.postMessage).not.toHaveBeenCalled();
	});

	it('stops listening when told', () => {
		const { send, listeners } = container();
		const go = vi.fn();
		answerOpen('/ui', go)();
		expect(listeners.size).toBe(0);
		send({ type: OPEN, url: '/ui/inbox' });
		expect(go).not.toHaveBeenCalled();
	});
});

describe('the worker, asking a window', () => {
	it('hears that the window goes there', async () => {
		const window = {
			postMessage: (message: unknown, [port]: Transferable[]) => {
				expect(message).toEqual({ type: OPEN, url: '/ui/inbox' });
				(port as MessagePort).postMessage({ taken: true });
			}
		};
		expect(await askToOpen(window, '/ui/inbox')).toBe(true);
	});

	it('gives up on a window that does not answer, so the address is loaded', async () => {
		vi.useFakeTimers();
		const asked = askToOpen({ postMessage: () => {} }, '/ui/inbox', 1000);
		await vi.advanceTimersByTimeAsync(1000);
		expect(await asked).toBe(false);
	});

	it('gives up on a window it cannot post to', async () => {
		const gone = {
			postMessage: () => {
				throw new Error('gone');
			}
		};
		expect(await askToOpen(gone, '/ui/inbox')).toBe(false);
	});
});
