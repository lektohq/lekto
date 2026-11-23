import { describe, expect, it, vi } from 'vitest';
import { events } from './events.svelte.ts';
import { FakeEventSource } from '#lib/testing/events.ts';

events.useFactory((url) => new FakeEventSource(url) as unknown as EventSource);

describe('event stream', () => {
	it('passes events on and reloads after a break', () => {
		const seen: string[] = [];
		const stop = events.subscribe((event) => seen.push(event.type));
		events.start(() => {});
		const source = FakeEventSource.last;
		expect(source.url).toBe('/api/v1/events');
		source.onopen?.();
		source.listeners.get('document.filed')?.({
			data: JSON.stringify({ type: 'document.filed', id: 'e1', occurred_at: '', document_id: 'd1' })
		});
		expect(seen).toEqual(['document.filed']);

		const before = events.generation;
		source.onerror?.();
		source.onopen?.();
		expect(events.generation).toBe(before + 1);

		source.listeners.get('document.updated')?.({ data: 'not json' });
		expect(seen).toHaveLength(1);
		stop();
		events.stop();
		expect(source.closed).toBe(true);
	});

	it("passes the admins' events to those listening for their type", () => {
		const documents: string[] = [];
		const trained: unknown[] = [];
		const stopDocuments = events.subscribe((event) => documents.push(event.type));
		const stop = events.on('classifier.trained', (event) => trained.push(event.number));
		events.start(() => {});
		FakeEventSource.last.send('classifier.trained', { number: 3 });
		expect(trained).toEqual([3]);
		expect(documents).toEqual([]);
		stop();
		FakeEventSource.last.send('classifier.trained', { number: 4 });
		expect(trained).toEqual([3]);
		stopDocuments();
		events.stop();
	});

	it('reports a stream the browser gave up on', () => {
		const closed = vi.fn();
		events.start(closed);
		const source = FakeEventSource.last;
		source.readyState = 2;
		source.onerror?.();
		expect(closed).toHaveBeenCalledOnce();
		expect(source.closed).toBe(true);
	});

	it('counts the first stream after a sign-out as no reconnect', () => {
		events.start(() => {});
		FakeEventSource.last.onopen?.();
		const before = events.generation;
		events.stop(); // sign-out
		events.start(() => {}); // sign-in
		FakeEventSource.last.onopen?.();
		expect(events.generation).toBe(before);
		events.stop();
	});

	it('reloads after a stream the server closed was started again', () => {
		events.start(() => {});
		FakeEventSource.last.onopen?.();
		const before = events.generation;
		FakeEventSource.last.readyState = 2;
		FakeEventSource.last.onerror?.(); // the API restarted: 502 from the proxy, the browser gave up
		events.start(() => {});
		FakeEventSource.last.onopen?.();
		expect(events.generation).toBe(before + 1);
		events.stop();
	});

	it('lets go of the stream of a hidden tab and counts its return as a reconnect (WP-02)', () => {
		const closed = vi.fn();
		events.start(closed);
		const first = FakeEventSource.last;
		first.onopen?.();
		const before = events.generation;
		events.pause();
		expect(first.readyState).toBe(2); // the connection is free for another tab
		expect(events.connected).toBe(false);
		expect(closed).not.toHaveBeenCalled(); // no failure: nothing asks the session
		events.start(closed);
		expect(FakeEventSource.last).not.toBe(first);
		FakeEventSource.last.onopen?.();
		// Shown again: the pages read anew what they missed.
		expect(events.generation).toBe(before + 1);
		events.stop();
	});
});
