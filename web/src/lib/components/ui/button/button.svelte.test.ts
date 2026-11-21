import { fireEvent, render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { createRawSnippet } from 'svelte';
import { describe, expect, it, vi } from 'vitest';
import Button from './button.svelte';

const children = createRawSnippet(() => ({ render: () => `<span>Speichern</span>` }));
const sources = import.meta.glob<string>('/src/**/*.svelte', {
	query: '?raw',
	import: 'default',
	eager: true
});

describe('a button while its action runs (WZ-01)', () => {
	it('is held and says so, but keeps the focus', async () => {
		// A button disabled while it works loses the focus to the page: after a dialog that
		// follows, the keyboard starts at the top again.
		const onclick = vi.fn();
		const props = $state({ children, onclick, busy: false });
		render(Button, props);
		const button = screen.getByRole('button', { name: 'Speichern' }) as HTMLButtonElement;
		button.focus();
		await userEvent.click(button);
		expect(onclick).toHaveBeenCalledTimes(1);

		props.busy = true;
		await vi.waitFor(() => expect(button.getAttribute('aria-disabled')).toBe('true'));
		expect(button.disabled).toBe(false);
		expect(document.activeElement).toBe(button);
		await userEvent.click(button);
		await userEvent.keyboard('{Enter}');
		expect(onclick).toHaveBeenCalledTimes(1);

		props.busy = false;
		await vi.waitFor(() => expect(button.hasAttribute('aria-disabled')).toBe(false));
		await userEvent.click(button);
		expect(onclick).toHaveBeenCalledTimes(2);
	});

	it('does not submit its form while it is held', async () => {
		const submitted = vi.fn((event: Event) => event.preventDefault());
		const form = document.createElement('form');
		form.addEventListener('submit', submitted);
		document.body.append(form);
		render(Button, { target: form, props: { children, type: 'submit', busy: true } });
		await fireEvent.click(screen.getByRole('button', { name: 'Speichern' }));
		expect(submitted).not.toHaveBeenCalled();
		form.remove();
	});

	it('is what every button of the app takes for it, never `disabled`', () => {
		const still = Object.entries(sources)
			.filter(([, source]) => /<Button\b[^>]*\bdisabled=\{busy\b/.test(source))
			.map(([path]) => path);
		expect(still).toEqual([]);
	});
});
