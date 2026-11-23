import { render, screen, waitFor, within } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { signIn } from '#lib/testing/session.ts';
import { m } from '#lib/paraglide/messages.js';
import { choose, selectedValue } from '#lib/testing/select.ts';
import { session } from '#lib/session.svelte.ts';
import WebhookForm from './WebhookForm.svelte';
import { fakeApi, json, recording, type Routes, type Sent } from '#lib/testing/api.ts';
import { webhookOf } from '#lib/testing/system.ts';

// What the form's guard asks before a navigation (`UnsavedGuard`), to try leaving.
const guards = vi.hoisted(() => [] as ((navigation: unknown) => void)[]);
vi.mock('$app/navigation', () => ({
	afterNavigate: vi.fn(),
	beforeNavigate: (guard: (navigation: unknown) => void) => guards.push(guard),
	goto: vi.fn()
}));

/** Whether leaving by a link is held back with the question, which is then answered "stay". */
async function heldBack(): Promise<boolean> {
	const cancel = vi.fn();
	guards.at(-1)?.({
		type: 'link',
		from: { url: new URL('http://lekto/ui/webhooks/hook/edit') },
		to: { url: new URL('http://lekto/ui/documents') },
		cancel
	});
	if (cancel.mock.calls.length === 0) return false;
	const question = await screen.findByRole('alertdialog', { name: m.unsaved_title() });
	await userEvent.click(within(question).getByRole('button', { name: m.cancel() }));
	await waitFor(() => expect(screen.queryByRole('alertdialog')).toBeNull());
	return true;
}

let fetchMock: ReturnType<typeof fakeApi>;
const sent: Sent[] = [];

const stored = webhookOf({
	owner_id: 'erika',
	name: 'HA',
	url: 'http://ha.lan:8123/api/webhook/lekto',
	headers: ['Authorization']
});

/** The API of the form: creating and changing the webhook `hook`, each request kept in `sent`;
 * `more` before these. */
function serve(more: Routes = {}) {
	const routes: Routes = {
		'POST /api/v1/webhooks': () => json({ ...stored, secret: null, signed: false }, 201),
		'PATCH /api/v1/webhooks/hook': () => ({ ...stored, signed: false }),
		'DELETE /api/v1/webhooks/hook/secret': () => ({ ...stored, signed: false }),
		'GET /api/v1/fields': () => [],
		...more
	};
	fetchMock = fakeApi(recording(routes, sent));
	vi.stubGlobal('fetch', fetchMock);
}

beforeEach(() => {
	signIn('user', { id: 'erika', username: 'erika' });
	sent.length = 0;
	serve();
});

afterEach(() => {
	session.clear();
});

describe('WebhookForm', () => {
	it('creates an unsigned webhook with a header of its own', async () => {
		const ondone = vi.fn();
		render(WebhookForm, { cancelHref: '/ui/webhooks', ondone });
		await userEvent.type(screen.getByLabelText(m.field_name()), 'HA');
		await userEvent.type(screen.getByLabelText(m.webhook_url()), stored.url);
		await userEvent.click(screen.getByRole('button', { name: m.webhook_header_add() }));
		await userEvent.type(screen.getByLabelText(m.webhook_header_name()), 'Authorization');
		const create = screen.getByRole('button', { name: m.create() });
		// A new header needs a value.
		expect((create as HTMLButtonElement).disabled).toBe(true);
		await userEvent.type(screen.getByLabelText(m.webhook_header_value()), 'Bearer t0ken');
		await userEvent.click(screen.getByLabelText(m.webhook_signed()));
		await userEvent.click(create);
		expect(sent).toEqual([
			{
				method: 'POST',
				path: '/api/v1/webhooks',
				body: {
					name: 'HA',
					url: stored.url,
					event_types: ['*'],
					active: true,
					signed: false,
					body: 'thin',
					body_template: null,
					max_open_tasks: 4,
					headers: [{ name: 'Authorization', value: 'Bearer t0ken' }]
				}
			}
		]);
		expect(ondone).toHaveBeenCalledWith('hook');
	});

	it('shows the secret of a signed webhook once, then goes on to its page', async () => {
		serve({ 'POST /api/v1/webhooks': () => json({ ...stored, secret: 'whsec_once' }, 201) });
		const ondone = vi.fn();
		render(WebhookForm, { cancelHref: '/ui/webhooks', ondone });
		await userEvent.type(screen.getByLabelText(m.field_name()), 'HA');
		await userEvent.type(screen.getByLabelText(m.webhook_url()), stored.url);
		await userEvent.click(screen.getByRole('button', { name: m.create() }));
		expect((await screen.findByTestId('secret')).textContent).toBe('whsec_once');
		expect(ondone).not.toHaveBeenCalled();
		await userEvent.click(screen.getByRole('button', { name: m.secret_done() }));
		expect(ondone).toHaveBeenCalledWith('hook');
	});

	it('keeps untouched headers out of a change and stops signing', async () => {
		render(WebhookForm, { webhook: stored, cancelHref: '/ui/webhooks/hook', ondone: () => {} });
		const value = await screen.findByLabelText(m.webhook_header_value());
		expect((value as HTMLInputElement).placeholder).toBe(m.webhook_header_kept());
		await userEvent.click(screen.getByLabelText(m.webhook_signed()));
		await userEvent.click(screen.getByRole('button', { name: m.save() }));
		expect(sent.map((item) => [item.method, item.path])).toEqual([
			['PATCH', '/api/v1/webhooks/hook'],
			['DELETE', '/api/v1/webhooks/hook/secret']
		]);
		expect(sent[0].body).not.toHaveProperty('headers');
	});

	it('asks a value of a kept header renamed, not of one only spelt otherwise (WC-K09)', async () => {
		const user = userEvent.setup();
		render(WebhookForm, { webhook: stored, cancelHref: '/ui/webhooks/hook', ondone: () => {} });
		const name = await screen.findByLabelText(m.webhook_header_name());
		const save = () => screen.getByRole('button', { name: m.save() }) as HTMLButtonElement;
		await user.clear(name);
		await user.type(name, 'authorization');
		expect(save().disabled).toBe(false); // the same header for HTTP
		expect((screen.getByLabelText(m.webhook_header_value()) as HTMLInputElement).placeholder).toBe(
			m.webhook_header_kept()
		);
		await user.clear(name);
		await user.type(name, 'X-Token');
		expect(save().disabled).toBe(true); // another header: no stored value to keep
		expect((screen.getByLabelText(m.webhook_header_value()) as HTMLInputElement).placeholder).toBe(
			''
		);
	});

	it('sends all headers when one changes, an empty value keeping the stored one', async () => {
		render(WebhookForm, { webhook: stored, cancelHref: '/ui/webhooks/hook', ondone: () => {} });
		await screen.findByLabelText(m.webhook_header_value());
		await userEvent.click(screen.getByRole('button', { name: m.webhook_header_add() }));
		const names = screen.getAllByLabelText(m.webhook_header_name());
		const values = screen.getAllByLabelText(m.webhook_header_value());
		await userEvent.type(names[1], 'X-Tenant');
		await userEvent.type(values[1], 'home');
		await userEvent.click(screen.getByRole('button', { name: m.save() }));
		expect((sent[0].body as { headers: unknown }).headers).toEqual([
			{ name: 'Authorization' },
			{ name: 'X-Tenant', value: 'home' }
		]);
	});

	it('sends a template body', async () => {
		render(WebhookForm, { webhook: stored, cancelHref: '/ui/webhooks/hook', ondone: () => {} });
		await screen.findByLabelText(m.webhook_header_value());
		await userEvent.click(screen.getByRole('button', { name: m.webhook_body_template() }));
		expect(screen.getByText(m.webhook_body_template_hint())).toBeTruthy();
		const save = screen.getByRole('button', { name: m.save() });
		expect((save as HTMLButtonElement).disabled).toBe(true);
	});

	it('changes how many tasks the webhook takes at a time', async () => {
		render(WebhookForm, { webhook: stored, cancelHref: '/ui/webhooks/hook', ondone: () => {} });
		const field = await screen.findByLabelText(m.webhook_open_tasks());
		await userEvent.clear(field);
		await userEvent.type(field, '65');
		const save = screen.getByRole('button', { name: m.save() });
		expect((save as HTMLButtonElement).disabled).toBe(true);
		await userEvent.clear(field);
		await userEvent.type(field, '8');
		await userEvent.click(save);
		expect((sent[0].body as { max_open_tasks: number }).max_open_tasks).toBe(8);
	});

	it('shows users no model call', async () => {
		render(WebhookForm, { cancelHref: '/ui/webhooks', ondone: () => {} });
		await screen.findByLabelText(m.field_name());
		expect(screen.queryByLabelText(m.webhook_model_call())).toBeNull();
	});

	it('lets an admin make a webhook serve as a model call, with its time to answer', async () => {
		signIn('admin', { id: 'erika', username: 'erika' });
		render(WebhookForm, { webhook: stored, cancelHref: '/ui/webhooks/hook', ondone: () => {} });
		const user = userEvent.setup();
		await choose(
			user,
			await screen.findByRole('combobox', { name: m.webhook_model_call() }),
			'propose'
		);
		const time = screen.getByLabelText(m.webhook_model_call_time());
		await user.clear(time);
		await user.type(time, '10');
		await user.click(screen.getByRole('button', { name: m.save() }));
		expect((sent[0].body as { model_call: unknown }).model_call).toEqual({
			kind: 'propose',
			timeout_seconds: 600
		});
	});

	it('lets an admin take the model call away', async () => {
		signIn('admin', { id: 'boss', username: 'boss' });
		const serving = { ...stored, model_call: { kind: 'extract' as const, timeout_seconds: 300 } };
		render(WebhookForm, { webhook: serving, cancelHref: '/ui/webhooks/hook', ondone: () => {} });
		const user = userEvent.setup();
		const field = await screen.findByRole('combobox', { name: m.webhook_model_call() });
		expect(selectedValue(field)).toBe('extract');
		await choose(user, field, '');
		await user.click(screen.getByRole('button', { name: m.save() }));
		expect((sent[0].body as { model_call: unknown }).model_call).toBeNull();
	});

	it('serves only rules when chosen so: no event at all', async () => {
		render(WebhookForm, { webhook: stored, cancelHref: '/ui/webhooks/hook', ondone: () => {} });
		await userEvent.click(screen.getByRole('button', { name: m.webhook_trigger_rules() }));
		expect(screen.queryByText(m.webhook_events_all())).toBeNull();
		expect(screen.getByText(m.webhook_trigger_rules_hint())).toBeTruthy();
		await userEvent.click(screen.getByRole('button', { name: m.save() }));
		expect(sent.at(-1)?.body).toMatchObject({ event_types: [] });
	});

	it('opens a webhook without events as one for rules, and events start with all of them', async () => {
		render(WebhookForm, {
			webhook: { ...stored, event_types: [] },
			cancelHref: '/ui/webhooks/hook',
			ondone: () => {}
		});
		expect(
			screen.getByRole('button', { name: m.webhook_trigger_rules() }).getAttribute('aria-pressed')
		).toBe('true');
		await userEvent.click(screen.getByRole('button', { name: m.webhook_trigger_events() }));
		expect((screen.getByLabelText(m.webhook_events_all()) as HTMLInputElement).checked).toBe(true);
	});

	it('asks for at least one event while not all are chosen', async () => {
		render(WebhookForm, { webhook: stored, cancelHref: '/ui/webhooks/hook', ondone: () => {} });
		await userEvent.click(screen.getByLabelText(m.webhook_events_all()));
		const save = screen.getByRole('button', { name: m.save() }) as HTMLButtonElement;
		expect(save.disabled).toBe(true);
		expect(screen.getByText(m.webhook_events_missing())).toBeTruthy();
		await userEvent.click(screen.getByLabelText(m.event_filed()));
		expect(save.disabled).toBe(false);
		await userEvent.click(save);
		expect(sent.at(-1)?.body).toMatchObject({ event_types: ['document.filed'] });
	});

	it('tells how often the chosen events come for one document', async () => {
		render(WebhookForm, { webhook: stored, cancelHref: '/ui/webhooks/hook', ondone: () => {} });
		expect(
			screen.getByText(new RegExp(m.webhook_volume_total_range({ least: 31, most: 75 })))
		).toBeTruthy();
		await userEvent.click(screen.getByLabelText(m.webhook_events_all()));
		expect(screen.getAllByText(m.webhook_volume_run({ count: 13 }))).toHaveLength(2);
		await userEvent.click(screen.getByLabelText(m.event_filed()));
		const line = screen.getByText(m.webhook_volume_total_exact({ count: 1 }));
		expect(line.textContent).not.toContain(m.webhook_volume_steps({ least: 26, most: 54 }));
	});

	describe('leaving with something changed', () => {
		const open = () =>
			render(WebhookForm, {
				webhook: { ...stored, model_call: null },
				cancelHref: '/ui/webhooks/hook',
				ondone: () => {}
			});

		it('asks nothing while the form is as it opened', async () => {
			open();
			expect(await heldBack()).toBe(false);
		});

		it('asks after a name was typed', async () => {
			open();
			await userEvent.type(screen.getByLabelText(m.field_name()), 'x');
			expect(await heldBack()).toBe(true);
		});

		it('asks nothing once what was typed is typed back', async () => {
			const user = userEvent.setup();
			open();
			const name = screen.getByLabelText(m.field_name());
			await user.type(name, 'x');
			await user.type(name, '{Backspace}');
			expect(await heldBack()).toBe(false);
		});

		// None of these sends an event of a form: the guard heard nothing of them once.
		it('asks after only the trigger was switched', async () => {
			open();
			await userEvent.click(screen.getByRole('button', { name: m.webhook_trigger_rules() }));
			expect(await heldBack()).toBe(true);
		});

		it('asks after only the kind of body was chosen', async () => {
			open();
			await userEvent.click(screen.getByRole('button', { name: m.webhook_body_full() }));
			expect(await heldBack()).toBe(true);
		});

		it('asks after only a header was removed', async () => {
			open();
			await userEvent.click(
				screen.getByRole('button', { name: m.webhook_header_remove({ name: 'Authorization' }) })
			);
			expect(await heldBack()).toBe(true);
		});

		it('asks after only the model call was chosen', async () => {
			signIn('admin', { id: 'erika', username: 'erika' });
			open();
			await choose(
				userEvent.setup(),
				await screen.findByRole('combobox', { name: m.webhook_model_call() }),
				'propose'
			);
			expect(await heldBack()).toBe(true);
		});

		it('asks nothing once saved', async () => {
			open();
			await userEvent.click(screen.getByRole('button', { name: m.webhook_trigger_rules() }));
			await userEvent.click(screen.getByRole('button', { name: m.save() }));
			await waitFor(() => expect(sent.length).toBeGreaterThan(0));
			expect(await heldBack()).toBe(false);
		});
	});
});
