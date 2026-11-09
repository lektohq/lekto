import { render, screen } from '@testing-library/svelte';
import { createRawSnippet } from 'svelte';
import { describe, expect, it } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import SectionTitle from './SectionTitle.svelte';

const text = (value: string) => createRawSnippet(() => ({ render: () => `<span>${value}</span>` }));

describe('SectionTitle', () => {
	it('stands alone without help', () => {
		render(SectionTitle, { size: 'card', children: text('Jobs') });
		expect(screen.getByRole('heading', { level: 2, name: 'Jobs' })).toBeTruthy();
		expect(screen.queryByRole('button')).toBeNull();
	});

	it('has its help beside it with tip', () => {
		render(SectionTitle, {
			size: 'card',
			tip: { name: 'Jobs', text: 'What the workers do.' },
			children: text('Jobs')
		});
		expect(screen.getByRole('heading', { level: 2, name: 'Jobs' })).toBeTruthy();
		expect(screen.getByRole('button', { name: m.hint_about({ name: 'Jobs' }) })).toBeTruthy();
	});
});
