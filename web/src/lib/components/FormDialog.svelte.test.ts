import { cleanup, render, screen, waitFor, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { createRawSnippet } from 'svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '#lib/api/problem.ts';
import { problemOf } from '#lib/testing/api.ts';
import { m } from '#lib/paraglide/messages.js';
import { phone } from '#lib/phone.svelte.ts';
import ChangeDialog from './ChangeDialog.svelte';
import EditorShell from './EditorShell.svelte';
import FormDialog from './FormDialog.svelte';

// A field that is told the error, as the dialogs' inputs are for `aria-invalid`.
const children = createRawSnippet((error: () => string | null) => ({
	render: () => `<input aria-label="Name" />`,
	setup(node) {
		$effect(() => node.setAttribute('aria-invalid', error() ? 'true' : 'false'));
	}
}));

const TAKEN = problemOf(409, { detail: 'taken' });
const taken = () => Promise.reject(new ApiError(409, TAKEN, null));

function dialog(action: () => Promise<void>) {
	const props = $state({ open: true, title: 'Space', submitLabel: 'Save', action, children });
	render(FormDialog, props);
	return props;
}

describe('FormDialog', () => {
	it('keeps the corner free for the X and runs the footer to the edge', async () => {
		dialog(() => Promise.resolve());
		const title = await screen.findByRole('heading', { name: 'Space' });
		// A title of two lines does not stick together, and ends before the X.
		expect(title.className).toContain('leading-snug');
		expect(title.closest('[data-slot="dialog-header"]')?.className).toContain('pr-8');
		// The footer's band takes back the padding of the content, on every side it touches.
		const content = document.querySelector('[data-slot="dialog-content"]');
		const footer = document.querySelector('[data-slot="dialog-footer"]');
		expect(content?.className).toMatch(/(?<![\w:-])p-5\b/);
		expect(footer?.className).toMatch(/(?<![\w:])-mx-5 -mb-5\b/);
		expect(footer?.className).toMatch(/(?<![\w:-])px-5\b/);
	});

	it('runs the action once, held while it runs, and closes when it succeeds', async () => {
		const user = userEvent.setup();
		let finish!: () => void;
		const action = vi.fn(() => new Promise<void>((resolve) => (finish = resolve)));
		const props = dialog(action);
		const save = await screen.findByRole('button', { name: 'Save' });
		await user.click(save);
		await user.click(save);
		expect(action).toHaveBeenCalledOnce();
		// Held, but not disabled: a disabled button would lose the focus to the page (WZ-01).
		expect(save.getAttribute('aria-disabled')).toBe('true');
		expect((save as HTMLButtonElement).disabled).toBe(false);
		expect(document.activeElement).toBe(save);
		// Nothing closes it while the action runs: not "Abbrechen", not the X, not Escape (WB-03).
		await user.click(screen.getByRole('button', { name: m.cancel() }));
		await user.click(screen.getByRole('button', { name: m.close() }));
		await user.keyboard('{Escape}');
		expect(props.open).toBe(true);
		expect(screen.getByRole('dialog')).toBeTruthy();
		finish();
		await waitFor(() => expect(props.open).toBe(false));
	});

	it('stays open with the error when the action fails, told to the fields too', async () => {
		const user = userEvent.setup();
		const props = dialog(vi.fn(taken));
		await user.click(await screen.findByRole('button', { name: 'Save' }));
		expect((await screen.findByRole('alert')).textContent).toContain('taken');
		expect(screen.getByLabelText('Name').getAttribute('aria-invalid')).toBe('true');
		expect(props.open).toBe(true);
		expect((screen.getByRole('button', { name: 'Save' }) as HTMLButtonElement).disabled).toBe(
			false
		);
		await user.click(screen.getByRole('button', { name: m.cancel() }));
		await waitFor(() => expect(props.open).toBe(false));
	});

	describe('closing over what was typed', () => {
		const question = () => screen.queryByRole('alertdialog', { name: m.unsaved_title() });

		it('asks before Escape drops it, and stays open on "Abbrechen" of the question', async () => {
			const user = userEvent.setup();
			const props = dialog(vi.fn());
			await user.type(await screen.findByLabelText('Name'), 'Haushalt');
			await user.keyboard('{Escape}');
			const asked = await screen.findByRole('alertdialog', { name: m.unsaved_title() });
			expect(props.open).toBe(true);
			await user.click(within(asked).getByRole('button', { name: m.cancel() }));
			await waitFor(() => expect(question()).toBeNull());
			expect(props.open).toBe(true);
			expect((screen.getByLabelText('Name') as HTMLInputElement).value).toBe('Haushalt');
		});

		it('closes once the person discards', async () => {
			const user = userEvent.setup();
			const props = dialog(vi.fn());
			await user.type(await screen.findByLabelText('Name'), 'Haushalt');
			await user.keyboard('{Escape}');
			const asked = await screen.findByRole('alertdialog', { name: m.unsaved_title() });
			await user.click(within(asked).getByRole('button', { name: m.unsaved_discard() }));
			await waitFor(() => expect(props.open).toBe(false));
		});

		it('asks before the X drops it', async () => {
			const user = userEvent.setup();
			const props = dialog(vi.fn());
			await user.type(await screen.findByLabelText('Name'), 'Haushalt');
			await user.click(screen.getByRole('button', { name: m.close() }));
			expect(await screen.findByRole('alertdialog', { name: m.unsaved_title() })).toBeTruthy();
			expect(props.open).toBe(true);
		});

		it('asks for an editor too, which says itself that it holds something (WT1-K17)', async () => {
			const user = userEvent.setup();
			const body = createRawSnippet(() => ({ render: () => `<p>Its fields</p>` }));
			const props = $state({ open: true, title: 'Kontakt', dirty: true, children: body });
			render(EditorShell as never, props as never);
			await screen.findByText('Its fields');
			await user.keyboard('{Escape}');
			const asked = await screen.findByRole('alertdialog', { name: m.unsaved_title() });
			expect(props.open).toBe(true);
			await user.click(within(asked).getByRole('button', { name: m.unsaved_discard() }));
			await waitFor(() => expect(props.open).toBe(false));
		});

		it('closes at once with nothing typed, and on "Abbrechen" with something typed', async () => {
			const user = userEvent.setup();
			const untouched = dialog(vi.fn());
			await screen.findByLabelText('Name');
			await user.keyboard('{Escape}');
			await waitFor(() => expect(untouched.open).toBe(false));
			expect(question()).toBeNull();
			cleanup();

			// "Abbrechen" says what the person wants: no question.
			const typed = dialog(vi.fn());
			await user.type(await screen.findByLabelText('Name'), 'Haushalt');
			await user.click(screen.getByRole('button', { name: m.cancel() }));
			await waitFor(() => expect(typed.open).toBe(false));
			expect(question()).toBeNull();
		});

		it('asks again in a dialog opened anew only once something is typed again', async () => {
			const user = userEvent.setup();
			const props = dialog(vi.fn());
			await user.type(await screen.findByLabelText('Name'), 'Haushalt');
			await user.click(screen.getByRole('button', { name: m.cancel() }));
			await waitFor(() => expect(props.open).toBe(false));
			props.open = true;
			await screen.findByLabelText('Name');
			await user.keyboard('{Escape}');
			await waitFor(() => expect(props.open).toBe(false));
			expect(question()).toBeNull();
		});

		it('does not ask where what is typed is nothing to lose (`guarded={false}`)', async () => {
			const user = userEvent.setup();
			const props = $state({
				open: true,
				title: 'Code',
				submitLabel: 'Save',
				action: vi.fn(),
				guarded: false,
				children
			});
			render(FormDialog, props);
			await user.type(await screen.findByLabelText('Name'), '123456');
			await user.keyboard('{Escape}');
			await waitFor(() => expect(props.open).toBe(false));
			expect(question()).toBeNull();
		});
	});

	describe('on a phone', () => {
		afterEach(() => phone.override(null));

		it('is a whole screen with the bar of the editors: cancel, title, submit', async () => {
			phone.override(true);
			const user = userEvent.setup();
			const action = vi.fn(() => Promise.resolve());
			const props = $state({
				open: true,
				title: 'Space',
				submitLabel: 'Delete',
				destructive: true,
				action,
				children
			});
			render(FormDialog, props);
			const submit = await screen.findByRole('button', { name: 'Delete' });
			expect(submit.className).toContain('text-destructive');
			expect(screen.getByRole('button', { name: m.cancel() })).toBeTruthy();
			expect(screen.getByRole('dialog').className).toContain('h-dvh');
			await user.click(submit);
			await waitFor(() => expect(props.open).toBe(false));
			expect(action).toHaveBeenCalledOnce();
		});
	});
});

describe('a dialog while its action runs (WB-03)', () => {
	// "Abbrechen", the X and Escape closed the dialog while "Speichern" ran: the request went
	// on and took effect all the same (a lens was saved, an action on many documents began).
	const body = createRawSnippet(() => ({ render: () => `<p>What it is about</p>` }));
	const FRAMES = [
		['FormDialog', FormDialog, { title: 'Space', children }],
		['EditorShell', EditorShell, { title: 'Space', children: body }],
		['ChangeDialog', ChangeDialog, { description: 'Nothing is stored yet.', children: body }]
	] as const;

	afterEach(() => phone.override(null));

	it.each(
		FRAMES.flatMap(([name, frame, given]) =>
			[false, true].map(
				(small) => [name, small ? 'on a phone' : 'wider', frame, given, small] as const
			)
		)
	)(
		'%s, %s: nothing closes it until the action ends',
		async (_name, _where, frame, given, small) => {
			phone.override(small);
			const user = userEvent.setup();
			let finish!: () => void;
			const action = vi.fn(() => new Promise<void>((resolve) => (finish = resolve)));
			const props = $state({ open: true, submitLabel: 'Save', action, ...given });
			render(frame as never, props as never);
			// A phone's bar names the submit of an editor by a short verb.
			const save = await screen.findByRole('button', { name: /^(Save|Speichern)$/ });
			await user.click(save);
			expect(action).toHaveBeenCalledOnce();

			const cancel = screen.getByRole('button', { name: m.cancel() });
			expect(cancel.getAttribute('aria-disabled')).toBe('true');
			await user.click(cancel);
			await user.keyboard('{Escape}');
			const close = screen.queryByRole('button', { name: m.close() });
			if (close) await user.click(close);
			expect(props.open).toBe(true);
			expect(screen.getByRole('dialog')).toBeTruthy();

			finish();
			await waitFor(() => expect(props.open).toBe(false));
		}
	);
});
