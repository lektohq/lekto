// The page that edits a rule: its editor only for who may change the rule (WF-05).
import { render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import { session } from '#lib/session.svelte.ts';
import { fakeApi, masterData } from '#lib/testing/api.ts';
import { goTo } from '#lib/testing/page-state.svelte.ts';
import { signIn } from '#lib/testing/session.ts';
import Page from './+page.svelte';

vi.mock('$app/navigation', () => import('#lib/testing/navigation.ts'));
vi.mock('$app/state', () => import('#lib/testing/app-state.ts'));

const rule = (changes: Record<string, unknown> = {}) => ({
	id: 'r1',
	name: 'Muster Versicherung',
	scope: 'global',
	space_id: null,
	enabled: true,
	version: 1,
	priority: 100,
	triggers: ['ingest'],
	conditions: { all: [], not: false },
	actions: [],
	managed_by_document_type_id: null,
	disabled_reason: null,
	disabled_reasons: [],
	...changes
});

const serve = (found: ReturnType<typeof rule>) =>
	vi.stubGlobal('fetch', fakeApi({ ...masterData(), 'GET /api/v1/rules/r1': () => found }));

beforeEach(() => goTo('/ui/rules/r1/edit', { id: 'r1' }));
afterEach(() => session.clear());

describe('the page that edits a rule', () => {
	it('gives an admin the editor', async () => {
		signIn('admin');
		serve(rule());
		render(Page);
		expect(await screen.findByDisplayValue('Muster Versicherung')).toBeTruthy();
		expect(screen.queryByRole('alert')).toBeNull();
	});

	it('says why instead of the editor to who may not change a global rule', async () => {
		signIn('user');
		serve(rule());
		render(Page);
		const alert = await screen.findByRole('alert');
		expect(alert.textContent).toContain(m.error_forbidden());
		expect(alert.textContent).toContain(
			m.reason_admins_only({ action: m.action_change_global_rules() })
		);
		expect(screen.queryByDisplayValue('Muster Versicherung')).toBeNull();
		// Trying again changes nothing; the way back is the rule.
		expect(screen.queryByRole('button', { name: m.retry() })).toBeNull();
		expect(screen.getByRole('link', { name: /Muster Versicherung/ }).getAttribute('href')).toBe(
			'/ui/rules/r1'
		);
	});

	it('sends even an admin to the type for the rule of a title pattern', async () => {
		signIn('admin');
		serve(rule({ managed_by_document_type_id: 't1' }));
		render(Page);
		const alert = await screen.findByRole('alert');
		expect(alert.textContent).toContain(
			m.reason_rule_follows_type({ type: 'Muster Versicherung' })
		);
		expect(screen.queryByDisplayValue('Muster Versicherung')).toBeNull();
		expect(
			screen.getByRole('button', { name: m.rule_title_pattern_of({ type: 'Muster Versicherung' }) })
		).toBeTruthy();
	});
});
