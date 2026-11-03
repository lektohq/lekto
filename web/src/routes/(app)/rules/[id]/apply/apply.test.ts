import { render, screen, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { goto } from '$app/navigation';
import type { components } from '#lib/api/schema.ts';
import { m } from '#lib/paraglide/messages.js';
import { session } from '#lib/session.svelte.ts';
import { calls, fakeApi, json } from '#lib/testing/documents.ts';
import { goTo } from '#lib/testing/page-state.svelte.ts';
import Page from './+page.svelte';

type Preview = components['schemas']['ApplyPreviewOut'];
type Application = components['schemas']['RuleApplicationOut'];

vi.mock('$app/navigation', () => ({ beforeNavigate: vi.fn(), goto: vi.fn() }));
vi.mock('$app/state', async () => ({
	page: (await import('#lib/testing/page-state.svelte.ts')).testPage
}));

const rule = {
	id: 'r1',
	name: 'Musterbank Depot',
	scope: 'global',
	space_id: null,
	enabled: false,
	version: 1
};

const row = (id: string): Preview['items'][number] => ({
	document_id: id,
	title: `Auszug ${id}`,
	changes: [{ field: 'title', old: 'alt', new: 'neu' }],
	conflicts: [],
	notes: [],
	sends: [],
	sends_refused: [],
	outcome: { space_id: 's1', chain: [] },
	accepted: null
});

const preview = (ids: string[], next: string | null): Preview => ({
	rule_id: 'r1',
	version: 1,
	items: ids.map(row),
	next_cursor: next,
	looked_at: 200,
	total: 800
});

const application = (status: Application['status']): Application => ({
	id: 'a1',
	rule_id: 'r1',
	version: 1,
	status,
	total: 1,
	done: 0,
	applied: 0,
	unchanged: 0,
	skipped: [],
	error: null,
	created_at: '2026-11-02T12:00:00Z',
	finished_at: null
});

/** A fake API whose preview pages answer only when `release` is called, one each. */
function held(pages: Preview[], routes: Parameters<typeof fakeApi>[0] = {}) {
	const waiting: (() => void)[] = [];
	const api = fakeApi({
		'GET /api/v1/rules/r1': () => rule,
		'POST /api/v1/rules/r1/apply/preview': async () => {
			const page = pages.shift();
			await new Promise<void>((resolve) => waiting.push(resolve));
			return json(page);
		},
		...routes
	});
	vi.stubGlobal('fetch', api);
	const previews = () => calls(api).filter((call) => call.endsWith('/apply/preview')).length;
	const release = async () => {
		await waitFor(() => expect(waiting.length).toBeGreaterThan(0));
		waiting.shift()?.();
	};
	return { api, previews, release };
}

const looked = (checked: string, count: string) =>
	m.rule_preview_loading({ checked, total: '800', count });

beforeEach(() => {
	goTo('/ui/rules/r1/apply', { id: 'r1' });
	session.user = { id: 'u1', role: 'admin' } as typeof session.user;
});

afterEach(() => {
	session.user = null;
	vi.unstubAllGlobals();
	vi.clearAllMocks();
});

describe("a rule's dry run", () => {
	it('shows how far it has come while pages without a hit go by', async () => {
		const { release } = held([
			preview([], 'c1'),
			preview([], 'c2'),
			preview(['a'], 'c3'),
			preview([], null)
		]);
		render(Page);

		expect(await screen.findByText(m.rule_preview_starting())).toBeTruthy();
		await release();
		expect(await screen.findByText(looked('200', '0'))).toBeTruthy();
		await release();
		expect(await screen.findByText(looked('400', '0'))).toBeTruthy();
		await release();
		expect(await screen.findByText(looked('600', '1'))).toBeTruthy();
		expect(
			screen.getByRole('checkbox', { name: m.rule_select_document({ title: 'Auszug a' }) })
		).toBeTruthy();
		const apply = screen.getByRole('button', { name: m.rule_apply_action() });
		expect((apply as HTMLButtonElement).disabled).toBe(true);

		await release();
		await waitFor(() => expect((apply as HTMLButtonElement).disabled).toBe(false));
		expect(screen.queryByRole('button', { name: m.rule_preview_stop() })).toBeNull();
	});

	it('stops after the page in flight, also before any hit, and goes on when asked', async () => {
		const { previews, release } = held([preview([], 'c1'), preview([], 'c2'), preview([], null)]);
		const user = userEvent.setup();
		render(Page);

		await user.click(await screen.findByRole('button', { name: m.rule_preview_stop() }));
		await release();
		const more = await screen.findByRole('button', { name: m.rule_preview_more() });
		expect(previews()).toBe(1);

		await user.click(more);
		await release();
		await release();
		expect(await screen.findByText(m.rule_preview_nothing())).toBeTruthy();
		expect(previews()).toBe(3);
		// Nothing to choose: no bar.
		expect(screen.queryByRole('button', { name: m.rule_apply_action() })).toBeNull();
	});

	it('keeps the application in the link and says what it waits for', async () => {
		const { release } = held([preview(['a'], null)], {
			'POST /api/v1/rules/r1/apply': () => application('queued'),
			'GET /api/v1/rule-applications/a1': () => application('queued'),
			'GET /api/v1/jobs/summary': () => ({
				kinds: [
					{ kind: 'pipeline.node', running: 1, due: 2, planned: 0, failed: 0, done: 0 },
					{ kind: 'rules.apply', running: 0, due: 1, planned: 0, failed: 0, done: 0 }
				],
				last_started_at: new Date().toISOString(),
				now: new Date().toISOString(),
				kept_since: '2026-10-26T12:00:00Z'
			})
		});
		const user = userEvent.setup();
		render(Page);

		await release();
		const apply = await screen.findByRole('button', { name: m.rule_apply_action() });
		await waitFor(() => expect((apply as HTMLButtonElement).disabled).toBe(false));
		await user.click(apply);

		expect(await screen.findByText(m.rule_apply_waiting())).toBeTruthy();
		expect(await screen.findByText(new RegExp(m.rule_apply_ahead({ count: '3' })))).toBeTruthy();
		expect(screen.getByRole('link', { name: m.rule_apply_jobs() })).toBeTruthy();
		expect(goto).toHaveBeenCalledWith('?application=a1', { replace: true, reset: false });
	});

	it('shows an application it comes back to, not a new dry run', async () => {
		const { previews } = held([], {
			'GET /api/v1/rule-applications/a1': () => ({
				...application('done'),
				done: 1,
				applied: 1,
				finished_at: '2026-11-02T12:00:05Z'
			})
		});
		goTo('/ui/rules/r1/apply?application=a1', { id: 'r1' });
		render(Page);

		expect(await screen.findByText(m.rule_apply_done())).toBeTruthy();
		expect(screen.getByRole('link', { name: m.rule_apply_back() })).toBeTruthy();
		expect(previews()).toBe(0);
	});
});
