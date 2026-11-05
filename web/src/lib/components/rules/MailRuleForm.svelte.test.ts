import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import type { DocumentType, Space, UserName } from '#lib/masterdata.svelte.ts';
import { formOf } from '#lib/mail-rules.ts';
import type { Mailbox } from '#lib/mailboxes.ts';
import { m } from '#lib/paraglide/messages.js';
import MailRuleForm from './MailRuleForm.svelte';

const mailboxes = [
	{ id: 'm1', name: 'Household', folders: ['INBOX'], status: { keywords: [] } }
] as unknown as Mailbox[];
const users = [{ id: 'u1', username: 'anna', display_name: 'Anna', active: true }] as UserName[];
const spaces = [
	{ id: 's1', name: 'Haushalt', personal_of: null, members: [{ user_id: 'u1', role: 'edit' }] },
	{ id: 's2', name: 'Fremd', personal_of: null, members: [] }
] as unknown as Space[];
const types = [{ id: 't1', name: 'E-Mail' }] as DocumentType[];

function show(errors: Record<string, string> = {}, form = formOf(null, 'm1', '')) {
	render(MailRuleForm, {
		form,
		mailboxes,
		users,
		spaces,
		types,
		errors,
		cancelHref: '/rules',
		onsubmit: vi.fn()
	});
	return form;
}

describe('the editor of a mail rule', () => {
	it('shows what is wrong under the block it belongs to', () => {
		const form = show({ name: 'no name', user: 'no person' });
		expect(screen.getByText('no name')).toBeTruthy();
		expect(screen.getByText('no person')).toBeTruthy();
		expect(screen.getByLabelText(m.field_name()).getAttribute('aria-invalid')).toBe('true');
		expect(form.conditions.items).toHaveLength(1);
	});

	it('keeps "Speichern und Probelauf" to be pressed, so that the problems get named', () => {
		show();
		const button = screen.getByRole('button', { name: m.rule_save() });
		expect(button.hasAttribute('disabled')).toBe(false);
	});

	it('names a space the person does not edit and says saving needs another', () => {
		const form = formOf(null, 'm1', '');
		form.userId = 'u1';
		form.spaceId = 's2';
		form.shown = ['space'];
		show({}, form);
		expect(screen.getByText(m.rule_space_unreachable_hint())).toBeTruthy();
	});
});
