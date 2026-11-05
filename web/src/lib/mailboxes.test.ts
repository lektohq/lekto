import { describe, expect, it } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
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
	statusOf,
	summaryOf,
	type Mailbox
} from './mailboxes.ts';

const MAILBOX: Mailbox = {
	id: 'm1',
	name: 'Household',
	host: 'imap.example.test',
	port: 993,
	security: 'tls',
	username: 'household@example.test',
	folders: ['INBOX', 'Rechnungen'],
	interval_minutes: 15,
	start: 'since_setup',
	since: null,
	fallback: 'everything',
	fallback_user_id: 'u1',
	body_type_id: 't1',
	enabled: true,
	status: {
		last_attempt_at: null,
		last_success_at: null,
		error: null,
		mails: 0,
		documents: 0,
		skipped_at: null,
		skipped: null,
		keywords: [],
		own_keywords: null
	},
	created_at: '2026-11-04T10:00:00Z',
	updated_at: '2026-11-04T10:00:00Z'
};

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
