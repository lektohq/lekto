// The styleguide renders every part it shows, each section with its title.
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import { fakeApi } from '#lib/testing/api.ts';
import Page from './+page.svelte';
import page from './+page.svelte?raw';

vi.mock('$app/navigation', () => import('#lib/testing/navigation.ts'));
vi.mock('$app/state', () => import('#lib/testing/app-state.ts'));

describe('the styleguide', () => {
	it('shows each section', () => {
		vi.stubGlobal('fetch', fakeApi());
		render(Page);
		// Every section the page names, as many as it has.
		const sections = [...new Set(page.match(/\bdev_section_\w+/g))];
		expect(sections.length).toBeGreaterThan(10);
		for (const key of sections) {
			const title = (m as unknown as Record<string, () => string>)[key]();
			expect(screen.getAllByRole('heading', { name: title }).length, key).toBeGreaterThan(0);
		}
		expect(screen.getAllByText(m.dev_sample_document()).length).toBeGreaterThan(1);
	});
});
