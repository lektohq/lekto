import { describe, expect, it } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import { MAX_MERGED, mergeBlock, mergeBlocked, type Candidate } from './merge.ts';

const document = (changes: Partial<Candidate> = {}): Candidate =>
	({
		id: 'doc-1',
		title: 'Grundsteuerbescheid 2026',
		original_filename: 'bescheid.pdf',
		media_type: 'application/pdf',
		access: 'edit',
		processing: { status: 'completed' },
		page_count: 3,
		created_at: '2026-11-08T09:12:00Z',
		...changes
	}) as Candidate;

describe('merge', () => {
	it('says why a document cannot join the stack', () => {
		expect(mergeBlock(document())).toBeNull();
		expect(mergeBlock(document(), ['doc-1'])).toBe(m.pick_blocked_in());
		expect(mergeBlock(document({ media_type: 'message/rfc822' }))).toBe(m.pick_blocked_mail());
		expect(
			mergeBlock(document({ processing: { status: 'processing' } as Candidate['processing'] }))
		).toBe(m.pick_blocked_processing());
		expect(mergeBlock(document({ access: 'read' }))).toBe(m.pick_blocked_rights());
		expect(mergeBlock(document({ page_count: null }))).toBe(m.pick_blocked_pages());
	});

	it('says why the chosen documents cannot be merged', () => {
		const scan = document({ id: 'doc-2', title: 'scan_0412' });
		expect(mergeBlocked([document(), scan], 2, false)).toBeNull();
		expect(mergeBlocked([document()], 1, false)).toBe(m.bulk_merge_two());
		expect(mergeBlocked([], 40, true)).toBe(m.bulk_merge_single());
		expect(mergeBlocked([], MAX_MERGED + 2, false)).toBe(
			m.bulk_merge_many({ count: String(MAX_MERGED + 1) })
		);
		expect(mergeBlocked([document(), { ...scan, access: 'read' }], 2, false)).toBe(
			m.bulk_merge_blocked({ title: 'scan_0412', reason: m.pick_blocked_rights() })
		);
	});
});
