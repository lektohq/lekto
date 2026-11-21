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
});
