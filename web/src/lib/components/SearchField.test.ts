import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { createRawSnippet } from 'svelte';
import { describe, expect, it, vi } from 'vitest';
import SearchField from './SearchField.svelte';

const end = createRawSnippet(() => ({ render: () => '<kbd data-testid="end">/</kbd>' }));

describe('SearchField', () => {
	it('hands its attributes and input to the search box and shows its end after it', async () => {
		const oninput = vi.fn();
		render(SearchField, { label: 'Search', oninput, end, 'data-page-search': '' });
		const box = screen.getByRole('searchbox', { name: 'Search' });
		expect(box.hasAttribute('data-page-search')).toBe(true);
		expect(box.compareDocumentPosition(screen.getByTestId('end'))).toBe(
			Node.DOCUMENT_POSITION_FOLLOWING
		);
		await userEvent.type(box, 'tax');
		expect(oninput).toHaveBeenCalledTimes(3);
	});

	it('is as high as every field, lower only in the filter panel, and keeps iOS from zooming', () => {
		const { unmount } = render(SearchField, { label: 'Search' });
		const box = screen.getByRole('searchbox');
		expect(box.closest('label')!.classList).toContain('h-11');
		expect(box.classList).toContain('text-base');
		unmount();
		render(SearchField, { label: 'Search', size: 'sm' });
		expect(screen.getByRole('searchbox').closest('label')!.classList).toContain('h-9');
	});
});
