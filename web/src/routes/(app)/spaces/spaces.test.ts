import { render, screen, waitFor, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { components } from '#lib/api/schema.ts';
import { m } from '#lib/paraglide/messages.js';
import { scope } from '#lib/scope.svelte.ts';
import { session } from '#lib/session.svelte.ts';
import { phone } from '#lib/phone.svelte.ts';
import { calls, fakeApi, json } from '#lib/testing/api.ts';
import { choose, selectedValue } from '#lib/testing/select.ts';
import Page from './+page.svelte';

type Space = components['schemas']['SpaceOut'];
type User = components['schemas']['UserOut'];

const USERS: User[] = [
	{ id: 'u1', username: 'john', role: 'user', active: true },
	{ id: 'u2', username: 'erika', role: 'user', active: true },
	{ id: 'u3', username: 'admin', role: 'admin', active: true }
] as User[];

const space = (id: string, changes: Partial<Space>): Space => ({
	id,
	name: 'Personal',
	personal_of: null,
	description: null,
	role: 'edit',
	members: [],
	created_at: '2026-10-21T08:00:00Z',
	version: 1,
	...changes
});

const HOUSE = space('house', {
	name: 'Haushalt',
	members: [
		{ user_id: 'u1', role: 'edit', username: 'john', active: true },
		{ user_id: 'u2', role: 'read', username: 'erika', active: true }
	]
});
const JOHN = space('john', {
	personal_of: 'u1',
	members: [{ user_id: 'u1', role: 'edit', username: 'john', active: true }]
});
const ERIKA = space('erika', {
	personal_of: 'u2',
	role: 'read',
	members: [
		{ user_id: 'u2', role: 'edit', username: 'erika', active: true },
		{ user_id: 'u1', role: 'read', username: 'john', active: true }
	]
});

function signIn(id: string, role: User['role'] = 'user') {
	session.start({
		user: { id, username: USERS.find((user) => user.id === id)?.username ?? id, role },
		method: 'password',
		expires_at: '2026-10-21T12:00:00Z',
		csrf_token: 'token'
	} as never);
}

function start(spaces: Space[]) {
	const api = fakeApi({
		'GET /api/v1/spaces': () => spaces,
		'GET /api/v1/users': () => USERS,
		'PUT /api/v1/spaces/house/members/u3': () => HOUSE,
		'DELETE /api/v1/spaces/house/members/u2': () => HOUSE,
		'POST /api/v1/spaces': () => HOUSE,
		'PATCH /api/v1/spaces/house': () => HOUSE,
		'PATCH /api/v1/spaces/john': () => JOHN
	});
	vi.stubGlobal('fetch', api);
	render(Page);
	return api;
}

beforeEach(() => signIn('u1'));
afterEach(() => {
	phone.override(null);
	scope.set(false);
	vi.unstubAllGlobals();
	session.clear();
});

describe('spaces', () => {
	it('lists the personal space first, then the others with members and role', async () => {
		start([HOUSE, ERIKA, JOHN]);
		const own = await screen.findByRole('region', { name: m.spaces_own() });
		const rows = within(own).getAllByRole('listitem');
		expect(rows.map((row) => row.textContent?.replace(/\s+/g, ' ').trim())).toEqual([
			`${m.space_personal()} ${m.space_only_you()}`,
			`Haushalt ${m.space_members_line({ names: m.space_member_reads({ name: 'erika' }) })}`,
			`erika ${m.space_personal()} ${m.space_role_read()} ${m.space_members_line({ names: 'erika' })}`
		]);
		expect(screen.queryByRole('region', { name: m.spaces_others() })).toBeNull();
		// Deleted in the editor, not in the row (web/DESIGN.md, "Lists").
		expect(screen.queryByRole('button', { name: m.space_delete({ name: 'Haushalt' }) })).toBeNull();
		// Members: of one's own personal space and of a space one edits, not of another's.
		expect(
			screen.getByRole('button', { name: m.space_members({ name: m.space_personal() }) })
		).toBeTruthy();
		expect(screen.queryByRole('button', { name: m.space_members({ name: 'erika' }) })).toBeNull();
	});

	it('shows an admin the spaces they are no member of apart, with all users included', async () => {
		signIn('u3', 'admin');
		scope.set(true);
		const admins = space('admins', {
			personal_of: 'u3',
			members: [{ user_id: 'u3', role: 'edit', username: 'admin', active: true }]
		});
		const api = start([HOUSE, JOHN, admins]);
		const others = await screen.findByRole('region', { name: m.spaces_others() });
		expect(within(others).getAllByRole('listitem')).toHaveLength(2);
		const lists = calls(api).filter((call) => call.startsWith('GET /api/v1/spaces'));
		expect(lists.at(-1)).toContain('all_users=true');
		// An admin chooses the members of another user's personal space.
		expect(
			within(others).getByRole('button', { name: m.space_members({ name: 'john' }) })
		).toBeTruthy();
	});

	it('shows an admin only their own spaces without all users, like everyone', async () => {
		signIn('u3', 'admin');
		const admins = space('admins', {
			personal_of: 'u3',
			members: [{ user_id: 'u3', role: 'edit', username: 'admin', active: true }]
		});
		const api = start([admins]);
		await screen.findByRole('heading', { name: m.spaces_own() });
		expect(screen.queryByRole('region', { name: m.spaces_others() })).toBeNull();
		const lists = calls(api).filter((call) => call.startsWith('GET /api/v1/spaces'));
		expect(lists.at(-1)).not.toContain('all_users');
	});

	it('adds and removes members; the last editor stays', async () => {
		signIn('u1');
		const user = userEvent.setup();
		const api = start([HOUSE, JOHN]);
		await user.click(
			await screen.findByRole('button', { name: m.space_members({ name: 'Haushalt' }) })
		);
		const dialog = await screen.findByRole('dialog');
		// john is the only editor: no role to change, nothing to remove.
		expect(
			within(dialog).queryByRole('button', { name: m.members_remove({ name: 'john' }) })
		).toBeNull();
		await user.click(
			within(dialog).getByRole('button', { name: m.members_remove({ name: 'erika' }) })
		);
		// Asked first.
		const ask = await screen.findByRole('alertdialog');
		await user.click(within(ask).getByRole('button', { name: m.members_remove_do() }));
		await waitFor(() => expect(calls(api)).toContain('DELETE /api/v1/spaces/house/members/u2'));
		await choose(user, within(dialog).getByLabelText(m.members_add()), 'u3');
		await user.click(within(dialog).getByRole('button', { name: m.members_grant() }));
		await waitFor(() => expect(calls(api)).toContain('PUT /api/v1/spaces/house/members/u3'));
		const put = api.mock.calls.find(([request]) => request.method === 'PUT')![0];
		expect(await put.json()).toEqual({ role: 'read' });
	});
	it.each([
		['wider than a phone', false],
		['on a phone', true]
	])('shows the stored role again when the API refuses another, %s (WC-06)', async (_, small) => {
		// The field kept the refused choice, and the same choice again asked for nothing.
		phone.override(small);
		const user = userEvent.setup();
		const api = fakeApi({
			'GET /api/v1/spaces': () => [HOUSE, JOHN],
			'GET /api/v1/users': () => USERS,
			'PUT /api/v1/spaces/house/members/u2': () =>
				json({ type: 'about:blank', title: 'Unprocessable', status: 422, detail: 'no' }, 422)
		});
		vi.stubGlobal('fetch', api);
		render(Page);
		await user.click(
			await screen.findByRole('button', { name: m.space_members({ name: 'Haushalt' }) })
		);
		const dialog = await screen.findByRole('dialog');
		const role = () => within(dialog).getByLabelText(m.members_role_of({ name: 'erika' }));
		const puts = () => calls(api).filter((call) => call.startsWith('PUT '));
		expect(selectedValue(role())).toBe('read');
		await choose(user, role(), 'edit');
		await waitFor(() => expect(puts()).toHaveLength(1));
		await waitFor(() => expect(selectedValue(role())).toBe('read'));
		await waitFor(() => expect((role() as HTMLButtonElement).disabled).toBe(false));
		await choose(user, role(), 'edit');
		await waitFor(() => expect(puts()).toHaveLength(2));
	});

	it('shows what belongs in a space, and creates one with its description', async () => {
		const user = userEvent.setup({ pointerEventsCheck: 0 });
		const api = start([{ ...HOUSE, description: 'Wohnung, Nebenkosten' }, JOHN]);
		expect(await screen.findByText('Wohnung, Nebenkosten')).toBeTruthy();
		await user.click(screen.getByRole('button', { name: m.space_new() }));
		const dialog = await screen.findByRole('dialog');
		await user.type(within(dialog).getByLabelText(m.field_name()), 'Auto');
		await user.type(
			within(dialog).getByLabelText(m.space_description()),
			'Versicherung, Werkstatt'
		);
		await user.click(within(dialog).getByRole('button', { name: m.create() }));
		await waitFor(() => expect(calls(api)).toContain('POST /api/v1/spaces'));
		const post = api.mock.calls.find(([request]) => request.method === 'POST')![0];
		expect(await post.json()).toEqual({ name: 'Auto', description: 'Versicherung, Werkstatt' });
	});

	it('describes the personal space without renaming it', async () => {
		const user = userEvent.setup({ pointerEventsCheck: 0 });
		const api = start([HOUSE, JOHN]);
		await user.click(
			await screen.findByRole('button', { name: m.space_edit({ name: m.space_personal() }) })
		);
		const dialog = await screen.findByRole('dialog');
		expect(within(dialog).queryByLabelText(m.field_name())).toBeNull();
		await user.type(within(dialog).getByLabelText(m.space_description()), 'Arbeit');
		await user.click(within(dialog).getByRole('button', { name: m.save() }));
		await waitFor(() => expect(calls(api)).toContain('PATCH /api/v1/spaces/john'));
		const patch = api.mock.calls.find(([request]) => request.method === 'PATCH')![0];
		expect(await patch.json()).toEqual({ description: 'Arbeit' });
	});

	it('renames a shared space with its description, and removes an emptied one', async () => {
		const user = userEvent.setup({ pointerEventsCheck: 0 });
		const api = start([{ ...HOUSE, description: 'alt' }, JOHN]);
		await user.click(
			await screen.findByRole('button', { name: m.space_edit({ name: 'Haushalt' }) })
		);
		const dialog = await screen.findByRole('dialog');
		const name = within(dialog).getByLabelText(m.field_name());
		await user.clear(name);
		await user.type(name, 'Zuhause');
		await user.clear(within(dialog).getByLabelText(m.space_description()));
		await user.click(within(dialog).getByRole('button', { name: m.save() }));
		await waitFor(() => expect(calls(api)).toContain('PATCH /api/v1/spaces/house'));
		const patch = api.mock.calls.find(([request]) => request.method === 'PATCH')![0];
		expect(await patch.json()).toEqual({ name: 'Zuhause', description: null });
	});

	it('lets a reader leave a space, after asking', async () => {
		signIn('u2');
		// A dialog of an earlier test may still leave the body without pointer events.
		const user = userEvent.setup({ pointerEventsCheck: 0 });
		const api = start([{ ...HOUSE, role: 'read' }, ERIKA]);
		// Not their own personal space.
		expect(
			screen.queryByRole('button', { name: m.space_leave({ name: m.space_personal() }) })
		).toBeNull();
		await user.click(
			await screen.findByRole('button', { name: m.space_leave({ name: 'Haushalt' }) })
		);
		const dialog = await screen.findByRole('alertdialog');
		await user.click(within(dialog).getByRole('button', { name: m.space_leave_action() }));
		await waitFor(() => expect(calls(api)).toContain('DELETE /api/v1/spaces/house/members/u2'));
	});

	it('keeps a deactivated member without a role to change, for removing', async () => {
		const user = userEvent.setup({ pointerEventsCheck: 0 });
		const gone = {
			...HOUSE,
			members: [
				{ user_id: 'u1', role: 'edit' as const, username: 'john', active: true },
				{ user_id: 'u9', role: 'read' as const, username: 'jane', active: false }
			]
		};
		start([gone, JOHN]);
		await user.click(
			await screen.findByRole('button', { name: m.space_members({ name: 'Haushalt' }) })
		);
		const dialog = await screen.findByRole('dialog');
		expect(within(dialog).getByText(m.user_inactive())).toBeTruthy();
		expect(within(dialog).queryByLabelText(m.members_role_of({ name: 'jane' }))).toBeNull();
		expect(
			within(dialog).getByRole('button', { name: m.members_remove({ name: 'jane' }) })
		).toBeTruthy();
	});

	it('opens the editor by the name of a space one edits, not of one one reads', async () => {
		start([HOUSE, ERIKA, JOHN]);
		const own = await screen.findByRole('region', { name: m.spaces_own() });
		await userEvent.click(within(own).getByRole('button', { name: 'Haushalt' }));
		expect(await screen.findByRole('dialog')).toBeTruthy();
		expect(within(own).queryByRole('button', { name: 'erika' })).toBeNull();
	});

	it('offers no editor for the personal space of another one edits along (WH-02)', async () => {
		// The API lets only its user and admins describe it; "edit" there means the documents.
		const lent = space('erika', {
			...ERIKA,
			role: 'edit',
			members: [
				{ user_id: 'u2', role: 'edit', username: 'erika', active: true },
				{ user_id: 'u1', role: 'edit', username: 'john', active: true }
			]
		});
		start([HOUSE, lent, JOHN]);
		const own = await screen.findByRole('region', { name: m.spaces_own() });
		expect(within(own).getByText('erika')).toBeTruthy();
		expect(within(own).queryByRole('button', { name: 'erika' })).toBeNull();
		expect(within(own).getByRole('button', { name: 'Haushalt' })).toBeTruthy();
	});
});
