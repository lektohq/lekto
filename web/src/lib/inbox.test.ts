import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import { getLocale, setLocale } from '#lib/paraglide/runtime.js';
import { signIn } from '#lib/testing/session.ts';
import { scope } from '#lib/scope.svelte.ts';
import { session } from '#lib/session.svelte.ts';
import { summaryOf } from '#lib/testing/documents.ts';
import { badgeLabel, badgeText, badgeTone, inbox } from './inbox.svelte.ts';
import { calls, fakeApi, json } from '#lib/testing/api.ts';

const summary = summaryOf;

describe('inbox badge', () => {
	it.each([
		[{ intervene: 1, review: 2, new: 3 }, 'red'],
		[{ review: 1, new: 3, processing: 1 }, 'yellow'],
		[{ new: 2 }, 'green'],
		[{ processing: 2 }, 'grey']
	] as const)('takes the colour of the worst lane in %o', (counts, tone) => {
		expect(badgeTone(summary(counts))).toBe(tone);
	});

	it('shows nothing while nothing is open', () => {
		expect(badgeTone(summary({ done: 4 }))).toBeNull();
		expect(badgeTone(null)).toBeNull();
	});

	it('names what is in it', () => {
		expect(badgeLabel(summary({ intervene: 1, review: 2, new: 1, processing: 1 }))).toBe(
			[
				m.inbox_badge_total({ count: 5 }),
				m.inbox_badge_red({ count: 1 }),
				m.inbox_badge_yellow({ count: 2 }),
				m.inbox_badge_new({ count: 1 }),
				m.inbox_badge_processing({ count: 1 })
			].join(', ')
		);
		expect(badgeLabel(summary({ new: 3 }))).toBe(
			`${m.inbox_badge_total({ count: 3 })}, ${m.inbox_badge_new({ count: 3 })}`
		);
	});

	it('writes its numbers as the language does (WG-06)', () => {
		const before = getLocale();
		setLocale('de', { reload: false });
		try {
			expect(badgeLabel(summary({ new: 12345 }))).toBe('12.345 im Posteingang, 12.345 neu');
		} finally {
			setLocale(before, { reload: false });
		}
	});

	it('cuts a long number short', () => {
		expect(badgeText(7)).toBe('7');
		expect(badgeText(99)).toBe('99');
		expect(badgeText(1234)).toBe('99+');
	});
});

describe('inbox summary', () => {
	let api = fakeApi();

	beforeEach(() => {
		signIn('admin', { id: 'admin', username: 'admin' });
		api = fakeApi({ 'GET /api/v1/inbox/summary': () => summary({ review: 1 }) });
		vi.stubGlobal('fetch', api);
	});

	afterEach(() => {
		inbox.stop();
		scope.set(false);
		session.clear();
	});

	it('is fetched for the scope chosen', async () => {
		scope.set(true);
		await inbox.refresh();
		expect(calls(api)[0]).toBe('GET /api/v1/inbox/summary?all_users=true');
		expect(inbox.open).toBe(1);
		expect(inbox.summary?.worst_lane).toBe('yellow');
	});

	it('counts the caller’s own inbox for the app’s icon, whatever the scope (WM-05)', async () => {
		// The counter may count everyone's; the icon carries what a notification sets.
		api = fakeApi({}, (_, url) =>
			url.pathname === '/api/v1/inbox/summary'
				? json(summary(url.searchParams.has('all_users') ? { review: 7 } : { review: 2 }))
				: json({})
		);
		vi.stubGlobal('fetch', api);
		scope.set(true);
		await inbox.refresh();
		expect(inbox.open).toBe(7);
		expect(inbox.own).toBe(2);
		expect(calls(api)).toEqual([
			'GET /api/v1/inbox/summary?all_users=true',
			'GET /api/v1/inbox/summary'
		]);

		// The caller's own scope: one request, the same number.
		scope.set(false);
		api.mockClear();
		await inbox.refresh();
		expect(inbox.own).toBe(2);
		expect(calls(api)).toEqual(['GET /api/v1/inbox/summary']);
	});

	it('keeps the last summary while the server cannot be reached', async () => {
		await inbox.refresh();
		expect(inbox.open).toBe(1);
		api.mockRejectedValue(new TypeError('Failed to fetch'));
		await expect(inbox.refresh()).resolves.toBeUndefined();
		expect(inbox.open).toBe(1);
		// It remembers why, for who has nothing to show without it (the overview's tile, WE-08).
		expect(inbox.failure).toBeInstanceOf(TypeError);
	});

	it('is fetched again when the window comes back into view', async () => {
		vi.useFakeTimers();
		try {
			inbox.start();
			await vi.runAllTimersAsync();
			const before = api.mock.calls.length;
			window.dispatchEvent(new Event('focus'));
			await vi.runAllTimersAsync();
			expect(api.mock.calls.length).toBe(before + 1);
		} finally {
			vi.useRealTimers();
		}
	});
});
