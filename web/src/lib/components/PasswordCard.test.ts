import { render } from '@testing-library/svelte';
import { afterEach, describe, expect, it } from 'vitest';
import { session } from '#lib/session.svelte.ts';
import { signIn } from '#lib/testing/session.ts';
import PasswordCard from './PasswordCard.svelte';

afterEach(() => session.clear());

describe('PasswordCard', () => {
	it('names the account a password manager keeps the new password for (WC-K22)', () => {
		signIn('user', { id: 'erika', username: 'erika' });
		const { container } = render(PasswordCard);
		const form = container.querySelector('form')!;
		const account = form.querySelector<HTMLInputElement>('input[autocomplete="username"]');
		expect(account?.value).toBe('erika');
		expect(account?.hidden).toBe(true);
	});
});
