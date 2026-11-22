/** A fake of the browser's event stream for tests, and the app's stream started on it. */
import { events } from '#lib/events.svelte.ts';

type Listener = (message: { data: string }) => void;

/** What the app opens as its `EventSource`: the listeners it adds, an event sent to them. */
export class FakeEventSource {
	/** The source opened last. */
	static last: FakeEventSource;
	onopen: (() => void) | null = null;
	onerror: (() => void) | null = null;
	readyState = 1;
	closed = false;
	readonly listeners = new Map<string, Listener>();

	constructor(readonly url: string) {
		FakeEventSource.last = this;
	}

	addEventListener(type: string, listener: Listener) {
		this.listeners.set(type, listener);
	}

	close() {
		this.closed = true;
		this.readyState = 2;
	}

	/** An event of `type` with `data`, as the API writes it. */
	send(type: string, data: object = {}) {
		this.listeners.get(type)?.({
			data: JSON.stringify({ type, id: crypto.randomUUID(), occurred_at: '', ...data })
		});
	}
}

/** Starts the app's event stream on a fake; the function sends an event to it. A test stops it
 * with `events.stop()`. */
export function streamEvents(): (type: string, data?: object) => void {
	events.useFactory((url) => new FakeEventSource(url) as unknown as EventSource);
	events.start(() => {});
	return (type, data = {}) => FakeEventSource.last.send(type, data);
}
