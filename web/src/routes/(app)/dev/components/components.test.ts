// The styleguide renders every part it shows, each section with its title.
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import { fakeApi } from '#lib/testing/api.ts';
import Page from './+page.svelte';

vi.mock('$app/navigation', () => import('#lib/testing/navigation.ts'));
vi.mock('$app/state', () => import('#lib/testing/app-state.ts'));

describe('the styleguide', () => {
	it('shows each section', () => {
		vi.stubGlobal('fetch', fakeApi());
		render(Page);
		for (const title of [
			m.dev_section_fields(),
			m.dev_section_states(),
			m.dev_section_dialogs(),
			m.dev_section_cards()
		])
			expect(screen.getAllByRole('heading', { name: title }).length).toBeGreaterThan(0);
		expect(screen.getAllByText(m.dev_sample_document()).length).toBeGreaterThan(1);
	});

	it('shows the parts the pages build on, each for itself (WF-08)', () => {
		vi.stubGlobal('fetch', fakeApi());
		render(Page);
		// A state with its icon, a rule's switch, a progress bar, the lenses, a page with its cut.
		const done = screen
			.getAllByText(m.jobs_state_done())
			.map((element) => element.closest('[data-slot="badge"]'))
			.find((badge) => badge !== null);
		expect(done?.querySelector('svg')).not.toBeNull();
		expect(screen.getAllByRole('switch').length).toBeGreaterThan(0);
		expect(screen.getAllByRole('progressbar').length).toBeGreaterThan(0);
		expect(screen.getAllByRole('link', { name: /Haushalt/ }).length).toBeGreaterThan(0);
		expect(screen.getByRole('button', { name: m.page_cut_after({ page: '1' }) })).toBeTruthy();
	});
});
