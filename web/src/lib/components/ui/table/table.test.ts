import { render } from '@testing-library/svelte';
import { createRawSnippet } from 'svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import Table from './table.svelte';

const rows = createRawSnippet(() => ({ render: () => '<tbody><tr><td>x</td></tr></tbody>' }));

/** jsdom lays nothing out: the container is as wide as it is told. */
function widths(scrollWidth: number, clientWidth: number) {
	vi.spyOn(HTMLElement.prototype, 'scrollWidth', 'get').mockReturnValue(scrollWidth);
	vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(clientWidth);
}

afterEach(() => vi.restoreAllMocks());

describe('a table wider than its room (WE-05)', () => {
	it('scrolls in a region with a name that the keyboard reaches', () => {
		widths(760, 301);
		const { container } = render(Table, { label: 'Jobs', children: rows });
		const room = container.querySelector('[data-slot="table-container"]')!;
		expect(room.getAttribute('role')).toBe('region');
		expect(room.getAttribute('aria-label')).toBe('Jobs');
		expect(room.getAttribute('tabindex')).toBe('0');
	});

	it('is no stop of the keyboard and no region where the table fits', () => {
		widths(300, 300);
		const { container } = render(Table, { label: 'Jobs', children: rows });
		const room = container.querySelector('[data-slot="table-container"]')!;
		expect(room.hasAttribute('tabindex')).toBe(false);
		expect(room.hasAttribute('role')).toBe(false);
	});
});
