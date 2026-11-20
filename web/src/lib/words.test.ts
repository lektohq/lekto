import { afterEach, describe, expect, it } from 'vitest';
import { session } from '#lib/session.svelte.ts';
import { stateWords, wordsState } from '#lib/words.ts';

function signIn(id: string) {
	session.start({
		user: { id, username: id, role: 'user' },
		method: 'password',
		expires_at: '2026-10-18T12:00:00Z',
		csrf_token: 'token'
	} as never);
}

afterEach(() => session.clear());

describe('the words of a history entry', () => {
	it('are those of the user who searched', () => {
		signIn('u1');
		expect(wordsState('Strom')).toEqual({ words: 'Strom', by: 'u1' });
		expect(stateWords(wordsState(' Strom '))).toBe('Strom');
		// A search for nothing is a search too: it stands against the words of a lens.
		expect(stateWords(wordsState(''))).toBe('');
	});

	it('count for no one else: the next to sign in in this browser gets none', () => {
		signIn('u1');
		const entry = wordsState('Strom');
		session.clear();
		expect(stateWords(entry)).toBeUndefined();
		signIn('u2');
		expect(stateWords(entry)).toBeUndefined();
		signIn('u1');
		expect(stateWords(entry)).toBe('Strom');
	});

	it('are none in an entry without words, or with words of no one', () => {
		signIn('u1');
		expect(stateWords({})).toBeUndefined();
		// As an entry kept them before it named their user.
		expect(stateWords({ words: 'Strom' })).toBeUndefined();
	});
});
