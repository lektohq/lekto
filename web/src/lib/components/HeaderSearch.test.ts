import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { goto } from '$app/navigation';
import { m } from '#lib/paraglide/messages.js';
import { signIn } from '#lib/testing/session.ts';
import { openLens } from '#lib/open-lens.svelte.ts';
import { offerPageSearch } from '#lib/page-search.ts';
import { session } from '#lib/session.svelte.ts';
import HeaderSearch from './HeaderSearch.svelte';

const state = vi.hoisted(() => ({
	url: new URL('http://lekto/ui/inbox'),
	entry: {} as App.PageState
}));
vi.mock('$app/navigation', () => import('#lib/testing/navigation.ts'));
vi.mock('$app/state', () => ({
	page: {
		get url() {
			return state.url;
		},
		get state() {
			return state.entry;
		}
	}
}));

const USER = 'u1';

/** The words go into the history entry, never into the address, with whose they are. */
const searching = (words: string) => ({ state: { words, by: USER }, persistState: true });

beforeEach(() => {
	vi.mocked(goto).mockClear();
	state.url = new URL('http://lekto/ui/inbox');
	state.entry = {};
	signIn('user', { id: USER });
});

afterEach(() => session.clear());

describe('HeaderSearch', () => {
	it('searches the documents with the words', async () => {
		render(HeaderSearch);
		const field = screen.getByRole('searchbox', { name: m.header_search_label() });
		await userEvent.type(field, ' Stromrechnung März {Enter}');
		expect(goto).toHaveBeenCalledWith('/ui/documents', searching('Stromrechnung März'));
	});

	it('names the lens the document view has open, and keeps it', async () => {
		state.url = new URL('http://lekto/ui/documents?lens=l1&tag=7');
		openLens.name = 'Zu bezahlen';
		try {
			render(HeaderSearch);
			const field = screen.getByRole('searchbox', { name: m.header_search_label() });
			expect(field.getAttribute('placeholder')).toBe(m.header_search_in({ name: 'Zu bezahlen' }));
			await userEvent.type(field, 'Strom{Enter}');
			expect(goto).toHaveBeenCalledWith('/ui/documents?lens=l1&tag=7', searching('Strom'));
		} finally {
			openLens.name = null;
		}
	});

	it('keeps the filters of the document view, the sort goes with the search', async () => {
		state.url = new URL('http://lekto/ui/documents?tag=7&sort=title');
		state.entry = { words: 'alt', by: USER };
		render(HeaderSearch);
		const field = screen.getByRole('searchbox', { name: m.header_search_label() });
		expect((field as HTMLInputElement).value).toBe('alt');
		await userEvent.clear(field);
		await userEvent.type(field, 'neu{Enter}');
		expect(goto).toHaveBeenCalledWith('/ui/documents?tag=7', searching('neu'));
	});

	it.each([
		['another user', { words: 'alt', by: 'u2' }],
		['no one', { words: 'alt' }]
	])('shows none of the words %s searched for in this browser', (_, entry) => {
		state.url = new URL('http://lekto/ui/documents');
		state.entry = entry;
		render(HeaderSearch);
		const field = screen.getByRole('searchbox', { name: m.header_search_label() });
		expect((field as HTMLInputElement).value).toBe('');
	});

	it('shows the words of a lens a plain link opened', () => {
		state.url = new URL('http://lekto/ui/documents?lens=l1');
		openLens.query = 'Strom';
		try {
			render(HeaderSearch);
			const field = screen.getByRole('searchbox', { name: m.header_search_label() });
			expect((field as HTMLInputElement).value).toBe('Strom');
		} finally {
			openLens.query = null;
		}
	});

	it('takes the focus on / unless one types elsewhere', async () => {
		render(HeaderSearch);
		const field = screen.getByRole('searchbox', { name: m.header_search_label() });
		await userEvent.keyboard('/');
		expect(document.activeElement).toBe(field);
		expect((field as HTMLInputElement).value).toBe('');
	});

	it('goes the magnifier’s way on / where the header shows no field (WB-08)', async () => {
		// A phone, and the widths at which the menu takes the field's room: the form is not drawn.
		render(HeaderSearch, { class: 'not-drawn' });
		const field = screen.getByRole('searchbox', { name: m.header_search_label() });
		(field.closest('form') as HTMLElement).style.display = 'none';
		vi.mocked(goto).mockClear();
		// Elsewhere: the documents page, with its own field in focus.
		await userEvent.keyboard('/');
		expect(document.activeElement).not.toBe(field);
		expect(goto).toHaveBeenCalledWith('/ui/documents#search');
		// On the documents page: its field, without opening the page anew.
		const show = vi.fn();
		const take = offerPageSearch(show);
		vi.mocked(goto).mockClear();
		await userEvent.keyboard('/');
		expect(show).toHaveBeenCalledOnce();
		expect(goto).not.toHaveBeenCalled();
		take();
	});
});
