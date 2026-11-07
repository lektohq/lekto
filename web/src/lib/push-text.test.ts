import { describe, expect, it } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import { type PushPayload, pushText } from '#lib/push-text.ts';

function payload(kind: string, params: Record<string, unknown>, locale = 'de'): PushPayload {
	return { kind, params, url: '/ui/inbox', badge: null, tag: null, locale };
}

describe('the words of a notification', () => {
	it('names how many documents wait, and their titles', () => {
		expect(pushText(payload('waiting', { count: 3, new: 2, titles: ['A', 'B'] }))).toEqual({
			title: m.push_waiting_many({ count: 3 }, { locale: 'de' }),
			body: 'A · B'
		});
		expect(pushText(payload('waiting', { count: 1, new: 1, titles: ['Abschlag'] })).title).toBe(
			'Ein Dokument wartet auf Dich'
		);
	});

	it('says only how many are new when titles are off', () => {
		expect(pushText(payload('waiting', { count: 5, new: 4, titles: [] }, 'en'))).toEqual({
			title: '5 documents wait for you',
			body: '4 new since the last notification'
		});
	});

	it('speaks the language the device subscribed in', () => {
		const notice = payload('mailbox_failed', { name: 'Rechnungen' });
		expect(pushText(notice).title).toBe('Postfach „Rechnungen“ meldet einen Fehler');
		expect(pushText({ ...notice, locale: 'en' }).title).toBe(
			'Mailbox “Rechnungen” reports an error'
		);
	});

	it('words the other notices and a test', () => {
		expect(pushText(payload('webhook_disabled', { name: 'HA' })).title).toBe(
			'Webhook „HA“ wurde abgeschaltet'
		);
		expect(pushText(payload('job_failed', {})).title).toBe('Ein Job hat aufgegeben');
		expect(pushText(payload('test', {})).title).toBe('Benachrichtigungen funktionieren');
		expect(pushText(payload('something new', {})).title).toBe('Benachrichtigungen funktionieren');
	});
});
