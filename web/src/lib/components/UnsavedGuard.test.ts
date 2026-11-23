import { render, screen, waitFor, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { gotoWithState } from '#lib/held-state.ts';
import { m } from '#lib/paraglide/messages.js';
import UnsavedGuard from './UnsavedGuard.svelte';

type Navigation = {
	type: string;
	delta?: number;
	from: { url: URL } | null;
	to: { url: URL } | null;
	cancel: () => void;
};

const kit = vi.hoisted(() => ({
	before: [] as ((navigation: Navigation) => void)[],
	after: [] as (() => void)[],
	goto: vi.fn(async () => {})
}));
vi.mock('$app/navigation', () => ({
	beforeNavigate: (guard: (navigation: Navigation) => void) => kit.before.push(guard),
	afterNavigate: (done: () => void) => kit.after.push(done),
	goto: kit.goto
}));

const HERE = new URL('http://lekto/ui/webhooks/hook/edit');
const LIST = new URL('http://lekto/ui/documents');

/** The person tries to leave; whether the guard held them back. */
function leave(to: URL, how: { type?: string; delta?: number } = {}): boolean {
	const cancel = vi.fn();
	kit.before.at(-1)?.({
		type: how.type ?? 'link',
		delta: how.delta,
		from: { url: HERE },
		to: { url: to },
		cancel
	});
	return cancel.mock.calls.length > 0;
}

async function discard() {
	const question = await screen.findByRole('alertdialog', { name: m.unsaved_title() });
	await userEvent.click(within(question).getByRole('button', { name: m.unsaved_discard() }));
}

describe('UnsavedGuard', () => {
	let go: ReturnType<typeof vi.spyOn>;

	beforeEach(() => {
		kit.before.length = 0;
		kit.after.length = 0;
		kit.goto.mockClear();
		go = vi.spyOn(history, 'go').mockImplementation(() => {});
	});

	afterEach(() => vi.restoreAllMocks());

	it('lets the person go while nothing changed', () => {
		render(UnsavedGuard, { dirty: false });
		expect(leave(LIST)).toBe(false);
		expect(screen.queryByRole('alertdialog')).toBeNull();
	});

	it('asks before a link leaves, and goes there on "Verwerfen"', async () => {
		render(UnsavedGuard, { dirty: true });
		expect(leave(LIST)).toBe(true);
		await discard();
		await waitFor(() => expect(kit.goto).toHaveBeenCalledWith(LIST));
		expect(go).not.toHaveBeenCalled();
	});

	it('goes back in the history where the back button led: no new entry', async () => {
		render(UnsavedGuard, { dirty: true });
		expect(leave(LIST, { type: 'popstate', delta: -1 })).toBe(true);
		await discard();
		await waitFor(() => expect(go).toHaveBeenCalledWith(-1));
		// A `goto` would add an entry, and a second "back" would return into the discarded form.
		expect(kit.goto).not.toHaveBeenCalled();
	});

	it('lets the navigation it let go on through without asking again, then guards again', async () => {
		render(UnsavedGuard, { dirty: true });
		leave(LIST, { type: 'popstate', delta: -2 });
		await discard();
		await waitFor(() => expect(go).toHaveBeenCalledWith(-2));
		// The browser goes back now: the same guard sees it.
		expect(leave(LIST, { type: 'popstate', delta: -2 })).toBe(false);
		// Arrived (where the form stays, a pane of the same page): the next leaving asks again.
		kit.after.at(-1)?.();
		expect(leave(LIST)).toBe(true);
	});

	it('guards again when the navigation it let go on fails (WC-K01)', async () => {
		kit.goto.mockRejectedValueOnce(new Error('the page could not load'));
		render(UnsavedGuard, { dirty: true });
		expect(leave(LIST)).toBe(true);
		await discard();
		await waitFor(() => expect(kit.goto).toHaveBeenCalledTimes(1));
		expect(leave(LIST)).toBe(true); // still on the form: asked again
	});

	it('carries on the state the held navigation had: the words of a search', async () => {
		render(UnsavedGuard, { dirty: true });
		const state = { words: 'Strom', by: 'u1' };
		// The header's search starts it; the guard holds it back.
		void gotoWithState(LIST, state);
		kit.goto.mockClear();
		expect(leave(LIST, { type: 'goto' })).toBe(true);
		await discard();
		await waitFor(() => expect(kit.goto).toHaveBeenCalledWith(LIST, { state, persistState: true }));
	});

	it('takes no state of a navigation to another address', async () => {
		render(UnsavedGuard, { dirty: true });
		void gotoWithState('http://lekto/ui/documents?tag=t1', { words: 'Strom' });
		kit.goto.mockClear();
		leave(LIST);
		await discard();
		await waitFor(() => expect(kit.goto).toHaveBeenCalledWith(LIST));
	});

	it('asks nothing of a move within the page that keeps the form', () => {
		render(UnsavedGuard, { dirty: true, keeps: () => true });
		expect(leave(new URL('http://lekto/ui/webhooks/hook/edit?pane=text'))).toBe(false);
	});
});
