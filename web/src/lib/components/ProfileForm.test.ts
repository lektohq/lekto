import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import type { ProfileData } from '#lib/profile.ts';
import { session } from '#lib/session.svelte.ts';
import ProfileForm from './ProfileForm.svelte';
import { fakeApi, json } from '#lib/testing/api.ts';

vi.mock('$app/navigation', () => ({ beforeNavigate: vi.fn(), goto: vi.fn() }));

let fetchMock = fakeApi();
const sent: { path: string; body: unknown }[] = [];

const stored = {
	user_id: 'anna',
	display_name: 'Anna Example',
	aliases: ['Anna Sample'],
	birth_date: '1980-06-15',
	email: 'anna@mail.example',
	identifiers: [{ kind: 'tax_id', value: '12345678911' }],
	numbers: [
		{
			contact_id: 'employer',
			kind: 'personnel_number',
			value: '12345',
			source: 'manual',
			topic_id: null
		},
		{
			contact_id: 'insurer',
			kind: 'customer_number',
			value: 'K2002',
			source: 'learned',
			topic_id: null
		},
		{
			contact_id: 'insurer',
			kind: 'customer_number',
			value: 'K3003',
			source: 'learned',
			topic_id: null
		}
	]
};

const contacts = [
	{ id: 'employer', name: 'Employer', topic_ids: [] },
	{ id: 'insurer', name: 'Insurer', topic_ids: [] }
];

const data = { profile: stored, contacts, topics: [] } as unknown as ProfileData;

beforeEach(() => {
	session.start({
		user: { id: 'anna', username: 'anna', role: 'user' },
		method: 'password',
		expires_at: '2026-10-14T12:00:00Z',
		csrf_token: 'token'
	});
	sent.length = 0;
	fetchMock = fakeApi();
	fetchMock.mockImplementation(async (request) => {
		const path = new URL(request.url).pathname;
		if (request.method === 'PATCH') {
			const body = await request.json();
			sent.push({ path, body });
			return json({ ...stored, ...body });
		}
		if (path.endsWith('/profile')) return json(stored);
		if (path.endsWith('/contacts')) return json(contacts);
		return json([]);
	});
	vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
	session.clear();
	vi.unstubAllGlobals();
});

describe('ProfileForm', () => {
	it('shows the own profile and saves what is in it', async () => {
		render(ProfileForm, { data });
		const name = await screen.findByLabelText(m.profile_display_name());
		expect((name as HTMLInputElement).value).toBe('Anna Example');
		expect(screen.getByText('Anna Sample')).toBeTruthy();
		expect(screen.getByText('12345678911')).toBeTruthy();
		await userEvent.click(
			screen.getByRole('button', { name: m.alias_remove({ name: 'Anna Sample' }) })
		);
		await userEvent.click(screen.getByRole('button', { name: m.profile_alias_chip() }));
		await userEvent.type(screen.getByLabelText(m.profile_alias_input()), 'Anna Muster{Enter}');
		await userEvent.clear(name);
		await userEvent.click(screen.getByRole('button', { name: m.save() }));
		expect(sent).toEqual([
			{
				path: '/api/v1/auth/me/profile',
				body: {
					display_name: null,
					aliases: ['Anna Muster'],
					birth_date: '1980-06-15',
					email: 'anna@mail.example',
					identifiers: [{ kind: 'tax_id', value: '12345678911' }],
					numbers: [{ contact_id: 'employer', kind: 'personnel_number', value: '12345' }],
					declined_numbers: []
				}
			}
		]);
	});

	it('takes over a number found for the user and declines another as not theirs', async () => {
		render(ProfileForm, { data });
		// One closed line per contact, with the kinds it holds.
		await userEvent.click(screen.getByRole('button', { name: /Insurer/ }));
		await userEvent.click(screen.getByRole('button', { name: /K2002/ }));
		await userEvent.click(screen.getByRole('button', { name: m.identifier_keep() }));
		await userEvent.click(screen.getByRole('button', { name: /K3003/ }));
		await userEvent.click(screen.getByRole('button', { name: m.number_not_mine() }));
		await userEvent.click(screen.getByRole('button', { name: m.save() }));
		const body = sent[0].body as Record<string, unknown>;
		expect(body.numbers).toEqual([
			{ contact_id: 'employer', kind: 'personnel_number', value: '12345' },
			{ contact_id: 'insurer', kind: 'customer_number', value: 'K2002' }
		]);
		expect(body.declined_numbers).toEqual([
			{ contact_id: 'insurer', kind: 'customer_number', value: 'K3003' }
		]);
	});

	it('edits another user’s profile for an admin', async () => {
		render(ProfileForm, { data, userId: 'bob' });
		await screen.findByLabelText(m.profile_display_name());
		await userEvent.click(screen.getByRole('button', { name: m.save() }));
		expect(sent.map((item) => item.path)).toEqual(['/api/v1/users/bob/profile']);
	});

	it('saves only the part it shows', async () => {
		const { unmount } = render(ProfileForm, { data, part: 'person' });
		expect(screen.queryByRole('button', { name: /Insurer/ })).toBeNull();
		await userEvent.click(screen.getByRole('button', { name: m.save() }));
		expect(Object.keys(sent[0].body as object).sort()).toEqual([
			'aliases',
			'birth_date',
			'display_name',
			'email',
			'identifiers'
		]);
		unmount();
		render(ProfileForm, { data, part: 'numbers' });
		expect(screen.queryByLabelText(m.profile_display_name())).toBeNull();
		await userEvent.click(screen.getByRole('button', { name: m.save() }));
		expect(Object.keys(sent[1].body as object).sort()).toEqual(['declined_numbers', 'numbers']);
	});
});
