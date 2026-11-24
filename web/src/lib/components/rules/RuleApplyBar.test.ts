import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import { bulkDocuments } from '#lib/bulk.ts';
import { m } from '#lib/paraglide/messages.js';
import RuleApplyBar from './RuleApplyBar.svelte';

const props = (changes: Record<string, unknown> = {}) => ({
	chosen: 31,
	allChosen: true,
	lookedAt: 33,
	total: 33,
	loaded: 33,
	conflicts: 2,
	limit: 500,
	loading: false,
	complete: true,
	offerSwitchOn: false,
	busy: false,
	application: null,
	waiting: null,
	rule: 'r1',
	onchoose: vi.fn(),
	onstop: vi.fn(),
	onmore: vi.fn(),
	onapply: vi.fn(),
	ondetails: vi.fn(),
	...changes
});

const said = () => screen.getByTestId('apply-said');

describe('what the bar of a dry run tells a screen reader (WD-12)', () => {
	it('says in a region that stays how the dry run ended, not every page of it', async () => {
		const { rerender } = render(
			RuleApplyBar,
			props({ loading: true, complete: false, loaded: 10 })
		);
		// The region is there before there is anything to say: one that comes with its text is
		// often not read.
		expect(said().getAttribute('aria-live')).toBe('polite');
		expect(said().textContent).toBe('');
		const region = said();
		await rerender(props());
		expect(said()).toBe(region);
		expect(said().textContent).toBe(
			`${m.rule_preview_total({ documents: bulkDocuments(33) })} · ${m.rule_preview_conflicts({ count: '2' })}`
		);
	});

	it('offers no "all" to choose where every document has a conflict (WD-K02)', () => {
		render(RuleApplyBar, props({ loaded: 3, conflicts: 3 }));
		const all = screen.getByRole('checkbox', { name: m.rule_preview_select_all() });
		expect((all as HTMLInputElement).disabled).toBe(true);
	});

	it('says that the dry run stopped, with how far it came', async () => {
		render(RuleApplyBar, props({ complete: false, lookedAt: 20, loaded: 7, conflicts: 0 }));
		expect(said().textContent).toBe(
			m.rule_preview_stopped({ checked: '20', total: '33', count: '7' })
		);
	});
});
