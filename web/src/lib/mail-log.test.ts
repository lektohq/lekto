import { describe, expect, it } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import {
	failedSteps,
	noteOf,
	stepsDone,
	takenText,
	viewCount,
	viewOf,
	waitingText,
	type MailItem,
	type MailSummary
} from './mail-log.ts';

const ITEM: MailItem = {
	id: 'r1',
	folder: 'INBOX',
	subject: 'Ihre Rechnung',
	sender: 'Stadtwerke <rechnung@stadtwerke.example>',
	sent_at: null,
	arrived_at: '2026-11-04T09:00:00Z',
	fetched_at: '2026-11-04T09:01:00Z',
	size: 1200,
	outcome: 'taken',
	reason: null,
	rule: 'Strom',
	rule_id: 'u1',
	decided_at: '2026-11-04T09:01:00Z',
	later: false,
	documents: [{ id: 'd1', title: 'Rechnung' }],
	documents_hidden: 0,
	steps: [
		{ action: 'read', value: null, failed: null },
		{
			action: 'add_keyword',
			value: 'Lekto',
			failed: { code: 'mail_server_error', params: { detail: 'no keywords' } }
		}
	],
	gone_at: null,
	forgotten: false,
	waiting: false,
	next_rule: null
};

describe('the log of a mailbox', () => {
	it('says who took a mail, afterwards too', () => {
		expect(takenText(ITEM)).toBe(m.mailbox_by_rule({ name: 'Strom' }));
		expect(takenText({ ...ITEM, rule: null, rule_id: null })).toBe(m.mailbox_by_fallback());
		const later = takenText({ ...ITEM, outcome: 'nothing', later: true });
		expect(later).toContain(m.mailbox_nothing_taken());
		expect(later).toContain(m.mailbox_later({ date: '' }).trim().split(' ')[0]);
		expect(takenText({ ...ITEM, outcome: 'no_rule' })).toBe('');
	});

	it('notes the rule that takes a waiting mail, and a mail gone', () => {
		const waiting = { ...ITEM, outcome: 'no_rule' as const, waiting: true };
		expect(noteOf({ ...waiting, next_rule: { id: 'u2', name: 'Test', enabled: true } })).toBe(
			m.mailbox_next_rule({ name: 'Test' })
		);
		expect(noteOf({ ...waiting, waiting: false, gone_at: '2026-11-06T07:00:00Z' })).toBe(
			m.mailbox_gone()
		);
		expect(noteOf(ITEM)).toBe('');
	});

	it('puts the steps done apart from a refused one', () => {
		expect(stepsDone(ITEM)).toBe(m.mail_rule_after_read());
		expect(failedSteps(ITEM)).toHaveLength(1);
		expect(failedSteps(ITEM)[0]).toContain(m.mail_rule_after_add_keyword({ keyword: 'Lekto' }));
	});

	it('counts the views and names the waiting mails by rule', () => {
		const summary: MailSummary = {
			counts: { taken: 3, nothing: 1, no_rule: 5, failed: 1 },
			rules: [],
			waiting: [
				{ rule: { id: 'u1', name: 'Test', enabled: true }, mails: 12 },
				{ rule: { id: 'u2', name: 'Rechnungen', enabled: true }, mails: 2 }
			],
			kept: 500
		};
		expect(viewCount(summary, 'all')).toBe(10);
		expect(viewCount(summary, 'taken')).toBe(4);
		expect(viewCount(summary, 'known')).toBe(0);
		expect(viewOf('nothing')).toBe('taken');
		expect(waitingText(summary)).toBe(
			m.mailbox_waiting_note({
				count: 14,
				rules: `${m.mailbox_waiting_rule({ name: 'Test', count: 12 })}, ${m.mailbox_waiting_rule({ name: 'Rechnungen', count: 2 })}`
			})
		);
		expect(waitingText({ ...summary, waiting: [] })).toBe('');
		const one = { ...summary, waiting: [{ ...summary.waiting[0], mails: 1 }] };
		expect(waitingText(one)).toBe(
			m.mailbox_waiting_note_one({ rules: m.mailbox_waiting_rule({ name: 'Test', count: 1 }) })
		);
	});
});
