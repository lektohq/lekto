import { describe, expect, it } from 'vitest';
import { DOCUMENT_EVENT_TYPES, NODE_EVENTS } from './events.svelte.ts';
import { listRefresh } from './list-events.ts';

describe('what an event means for a list of documents (WP-03)', () => {
	const shown = (id: string) => id === 'on-the-page';

	it('reads everything anew for an event that may change what the list holds', () => {
		const changing = DOCUMENT_EVENT_TYPES.filter((type) => !NODE_EVENTS.has(type));
		expect(changing).toEqual(
			expect.arrayContaining([
				'document.lane_changed',
				'document.filed',
				'document.updated',
				'document.deleted'
			])
		);
		for (const type of changing) {
			expect(listRefresh({ type, document_id: 'elsewhere' }, shown)).toBe('all');
		}
	});

	it('reads only the rows for a step of a document the list shows, nothing for another', () => {
		// A document being processed sends a dozen of these: they change no count and no facet.
		expect(NODE_EVENTS.size).toBeGreaterThan(0);
		for (const type of NODE_EVENTS) {
			expect(listRefresh({ type, document_id: 'on-the-page' }, shown)).toBe('rows');
			expect(listRefresh({ type, document_id: 'elsewhere' }, shown)).toBe('none');
		}
	});
});
