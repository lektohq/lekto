/**
 * The mailboxes Lekto fetches from (System › Eingangskanäle › Mail; Tobi, 04.11.2026): how a
 * mailbox's state reads, its interval and folders in words, and the form of its dialog as the
 * API takes it.
 */
import type { components } from '#lib/api/schema.ts';
import { formatDate } from '#lib/i18n.ts';
import { m } from '#lib/paraglide/messages.js';

export type Mailbox = components['schemas']['MailboxOut'];
export type MailboxCreate = components['schemas']['MailboxCreate'];
export type MailboxPatch = components['schemas']['MailboxPatch'];
export type MailSecurity = components['schemas']['MailSecurity'];
export type FetchStart = components['schemas']['FetchStart'];
export type ConnectionTest = components['schemas']['ConnectionTestOut'];

export const INBOX = 'INBOX';

/** The usual port of each kind of security. */
export const DEFAULT_PORTS: Record<MailSecurity, number> = { tls: 993, starttls: 143, none: 143 };

/** The intervals offered, in minutes. */
export const INTERVALS = [1, 5, 15, 30, 60, 180, 720, 1440] as const;

/** The fallback "nothing" in the one choice of the fallback and its person. */
export const NOTHING = 'nothing';

/** A folder as a person reads it: the inbox in their language, the rest as the server names it. */
export function folderLabel(name: string): string {
	return name.toUpperCase() === INBOX ? m.mail_folder_inbox() : name;
}

/** "every 5 minutes", "every hour", "once a day". */
export function intervalLabel(minutes: number): string {
	if (minutes === 1) return m.mail_interval_minute();
	if (minutes < 60) return m.mail_interval_minutes({ count: minutes });
	if (minutes === 60) return m.mail_interval_hour();
	if (minutes === 1440) return m.mail_interval_day();
	if (minutes % 60 === 0) return m.mail_interval_hours({ count: minutes / 60 });
	return m.mail_interval_minutes({ count: minutes });
}

/** The intervals to choose from, with the mailbox's own where it is none of them. */
export function intervalOptions(current: number): { value: string; label: string }[] {
	const minutes: number[] = [...INTERVALS];
	if (!minutes.includes(current)) minutes.push(current);
	return minutes
		.sort((a, b) => a - b)
		.map((value) => ({ value: String(value), label: intervalLabel(value) }));
}

export type StatusTone = 'green' | 'red' | 'muted';

/** The state of a mailbox's fetches as its badge shows it. */
export function statusOf(mailbox: Mailbox): { tone: StatusTone; label: string } {
	if (mailbox.status.error) return { tone: 'red', label: m.mail_status_failing() };
	if (mailbox.status.last_success_at) return { tone: 'green', label: m.mail_status_ok() };
	return { tone: 'muted', label: m.mail_status_never() };
}

/** The line under a mailbox's name: server, folders, interval, the last fetch, counts. */
export function summaryOf(mailbox: Mailbox): string {
	const parts = [
		mailbox.host,
		mailbox.folders.map(folderLabel).join(', '),
		intervalLabel(mailbox.interval_minutes)
	];
	const { last_attempt_at: tried, last_success_at: worked, mails, documents } = mailbox.status;
	if (worked) parts.push(m.mail_last_success({ when: moment(worked) }));
	else if (tried) parts.push(m.mail_last_attempt({ when: moment(tried) }));
	if (mails > 0) parts.push(m.mail_counts({ mails, documents }));
	return parts.join(' · ');
}

function moment(value: string): string {
	return formatDate(value, { dateStyle: 'medium', timeStyle: 'short' });
}

/** What the dialog of a mailbox holds. */
export interface MailboxForm {
	name: string;
	host: string;
	port: string;
	security: MailSecurity;
	username: string;
	/** Empty: the stored one stays (a mailbox being changed). */
	password: string;
	folders: string[];
	interval: string;
	start: FetchStart;
	since: string;
	/** `NOTHING` or the id of the person everything is taken for. */
	fallback: string;
	bodyTypeId: string;
}

export function formOf(mailbox: Mailbox | null): MailboxForm {
	if (!mailbox) {
		return {
			name: '',
			host: '',
			port: String(DEFAULT_PORTS.tls),
			security: 'tls',
			username: '',
			password: '',
			folders: [INBOX],
			interval: '5',
			start: 'since_setup',
			since: '',
			fallback: NOTHING,
			bodyTypeId: ''
		};
	}
	return {
		name: mailbox.name,
		host: mailbox.host,
		port: String(mailbox.port),
		security: mailbox.security,
		username: mailbox.username,
		password: '',
		folders: [...mailbox.folders],
		interval: String(mailbox.interval_minutes),
		start: mailbox.start,
		since: mailbox.since ?? '',
		fallback: mailbox.fallback === 'everything' ? (mailbox.fallback_user_id ?? NOTHING) : NOTHING,
		bodyTypeId: mailbox.body_type_id ?? ''
	};
}

/** Whether the form can be saved: everything it needs is there. */
export function complete(form: MailboxForm, creating: boolean): boolean {
	const port = Number(form.port);
	return (
		form.name.trim() !== '' &&
		form.host.trim() !== '' &&
		Number.isInteger(port) &&
		port >= 1 &&
		port <= 65535 &&
		form.username.trim() !== '' &&
		(!creating || form.password !== '') &&
		form.folders.length > 0 &&
		(form.start !== 'since_date' || form.since !== '')
	);
}

function settings(form: MailboxForm) {
	const everything = form.fallback !== NOTHING;
	return {
		folders: form.folders,
		interval_minutes: Number(form.interval),
		start: form.start,
		since: form.start === 'since_date' ? form.since : null,
		fallback: everything ? ('everything' as const) : ('nothing' as const),
		fallback_user_id: everything ? form.fallback : null,
		body_type_id: form.bodyTypeId || null
	};
}

export function createBody(form: MailboxForm): MailboxCreate {
	return {
		name: form.name.trim(),
		host: form.host.trim(),
		port: Number(form.port),
		security: form.security,
		username: form.username.trim(),
		password: form.password,
		...settings(form)
	};
}

/** Everything the form holds; the password only when one was typed. */
export function patchBody(form: MailboxForm): MailboxPatch {
	return {
		name: form.name.trim(),
		host: form.host.trim(),
		port: Number(form.port),
		security: form.security,
		username: form.username.trim(),
		...(form.password ? { password: form.password } : {}),
		...settings(form)
	};
}

/** The port after the security changed: the new usual one where the old usual one stood. */
export function portAfter(form: MailboxForm, security: MailSecurity): string {
	return form.port === String(DEFAULT_PORTS[form.security])
		? String(DEFAULT_PORTS[security])
		: form.port;
}
