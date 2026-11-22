import { describe, expect, it } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import type { Reason } from '#lib/reasons.ts';
import {
	complete,
	createBody,
	folderLabel,
	formOf,
	intervalLabel,
	intervalOptions,
	NOTHING,
	patchBody,
	portAfter,
	cautions,
	statusOf,
	summaryOf,
	type Mailbox
} from './mailboxes.ts';
import { mailboxOf } from '#lib/testing/system.ts';

const MAILBOX = mailboxOf({
	name: 'Household',
	username: 'household@example.test',
	folders: ['INBOX', 'Rechnungen'],
	interval_minutes: 15,
	fallback: 'everything',
	fallback_user_id: 'u1',
	body_type_id: 't1'
});

describe('a mailbox in words', () => {
	it('names the inbox in the language of the UI, the rest as the server does', () => {
		expect(folderLabel('INBOX')).toBe(m.mail_folder_inbox());
		expect(folderLabel('Rechnungen')).toBe('Rechnungen');
	});

	it('says how often it fetches', () => {
		expect(intervalLabel(1)).toBe(m.mail_interval_minute());
		expect(intervalLabel(15)).toBe(m.mail_interval_minutes({ count: 15 }));
		expect(intervalLabel(60)).toBe(m.mail_interval_hour());
		expect(intervalLabel(180)).toBe(m.mail_interval_hours({ count: 3 }));
		expect(intervalLabel(1440)).toBe(m.mail_interval_day());
		expect(intervalOptions(7).map((option) => option.value)).toEqual([
			'1',
			'5',
			'7',
			'15',
			'30',
			'60',
			'180',
			'720',
			'1440'
		]);
	});

	it('tells the state of its fetches', () => {
		expect(statusOf(MAILBOX)).toEqual({ tone: 'muted', label: m.mail_status_never() });
		const fine = {
			...MAILBOX,
			status: { ...MAILBOX.status, last_success_at: '2026-11-04T11:00:00Z' }
		};
		expect(statusOf(fine).tone).toBe('green');
		const failing = {
			...fine,
			status: { ...fine.status, error: { code: 'mail_login_failed' as const, params: {} } }
		};
		expect(statusOf(failing).tone).toBe('red');
		expect(summaryOf(MAILBOX)).toBe(
			`imap.example.test · ${m.mail_folder_inbox()}, Rechnungen · ${m.mail_interval_minutes({ count: 15 })}`
		);
	});
});

describe('the form of a mailbox', () => {
	it('starts with the defaults for a new one', () => {
		const form = formOf(null);
		expect([form.port, form.security, form.folders, form.interval, form.fallback]).toEqual([
			'993',
			'tls',
			['INBOX'],
			'5',
			NOTHING
		]);
		expect(complete(form, true)).toBe(false);
		const filled = { ...form, name: 'Mine', host: 'imap.test', username: 'me', password: 'pw' };
		expect(complete(filled, true)).toBe(true);
		expect(complete({ ...filled, start: 'since_date' }, true)).toBe(false);
		expect(createBody(filled)).toMatchObject({
			name: 'Mine',
			port: 993,
			password: 'pw',
			fallback: 'nothing',
			fallback_user_id: null,
			body_type_id: null,
			since: null
		});
	});

	it('keeps the stored password unless one is typed', () => {
		const form = formOf(MAILBOX);
		expect(form.fallback).toBe('u1');
		expect(complete(form, false)).toBe(true);
		expect(patchBody(form)).not.toHaveProperty('password');
		expect(patchBody({ ...form, password: 'new' })).toMatchObject({ password: 'new' });
		expect(patchBody(form)).toMatchObject({
			fallback: 'everything',
			fallback_user_id: 'u1',
			body_type_id: 't1'
		});
	});

	it('moves the port along with the security where it was the usual one', () => {
		const form = formOf(null);
		expect(portAfter(form, 'starttls')).toBe('143');
		expect(portAfter({ ...form, port: '1993' }, 'starttls')).toBe('1993');
	});
});

describe('what a mailbox left out or could not do', () => {
	it('says nothing while all went well', () => {
		expect(cautions(MAILBOX)).toEqual([]);
	});

	it('names the step that failed and the mail left out, with when', () => {
		const reason: Reason = { code: 'mail_server_error', params: { detail: 'no' } };
		const mailbox: Mailbox = {
			...MAILBOX,
			status: {
				...MAILBOX.status,
				step_failed_at: '2026-11-05T10:00:00Z',
				step_failed: reason,
				skipped_at: '2026-11-04T10:00:00Z',
				skipped: reason
			}
		};
		expect(cautions(mailbox).map((item) => item.key)).toEqual(['step', 'skipped']);
		expect(cautions(mailbox)[0].text).toContain('2026');
	});
});
