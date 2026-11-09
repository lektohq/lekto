import { render } from '@testing-library/svelte';
import { createRawSnippet } from 'svelte';
import { describe, expect, it } from 'vitest';
import EmptyNote from './EmptyNote.svelte';

const words = createRawSnippet(() => ({ render: () => '<span>Nothing here</span>' }));
const icon = createRawSnippet(() => ({ render: () => '<svg data-testid="icon"></svg>' }));

describe('EmptyNote', () => {
	it('shows an icon above its words, the owl in its place where it has one', () => {
		const { container, getByTestId, unmount } = render(EmptyNote, { children: words, icon });
		expect(getByTestId('icon').compareDocumentPosition(container.querySelector('p')!)).toBe(
			Node.DOCUMENT_POSITION_FOLLOWING
		);
		unmount();
		const owl = render(EmptyNote, { children: words, icon, mascot: true });
		expect(owl.queryByTestId('icon')).toBeNull();
	});

	it('is smaller inside a dialog and hands its attributes to the box', () => {
		const { container } = render(EmptyNote, { children: words, size: 'sm', role: 'presentation' });
		const box = container.firstElementChild!;
		expect(box.classList).toContain('py-6');
		expect(box.classList).not.toContain('py-16');
		expect(box.getAttribute('role')).toBe('presentation');
	});
});
