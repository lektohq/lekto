import { m } from '#lib/paraglide/messages.js';

/**
 * The words of a notification (web/DESIGN.md, "App"). The server sends data only (its kind and
 * parameters, `services.push`); the service worker words it here in the device's language, the
 * one the web UI spoke when the device subscribed.
 */
export interface PushPayload {
	kind: string;
	params: Record<string, unknown>;
	url: string;
	badge: number | null;
	tag: string | null;
	locale: string;
}

export interface PushText {
	title: string;
	body: string;
}

type Locale = 'de' | 'en';

function text(value: unknown): string {
	return typeof value === 'string' ? value : '';
}

function count(value: unknown): number {
	return typeof value === 'number' && Number.isFinite(value) ? value : 0;
}

export function pushText(payload: PushPayload): PushText {
	const options = { locale: (payload.locale === 'de' ? 'de' : 'en') as Locale };
	const params = payload.params ?? {};
	switch (payload.kind) {
		case 'waiting': {
			const waiting = Math.max(1, count(params.count));
			const fresh = count(params.new);
			const titles = Array.isArray(params.titles) ? params.titles.map(text).filter(Boolean) : [];
			const title =
				waiting === 1
					? m.push_waiting_one({}, options)
					: m.push_waiting_many({ count: waiting }, options);
			const body = titles.length
				? titles.join(' · ')
				: fresh > 1
					? m.push_waiting_new({ count: fresh }, options)
					: '';
			return { title, body };
		}
		case 'webhook_disabled':
			return {
				title: m.push_webhook_disabled_title({ name: text(params.name) }, options),
				body: m.push_webhook_disabled_body({}, options)
			};
		case 'mailbox_failed':
			return {
				title: m.push_mailbox_failed_title({ name: text(params.name) }, options),
				body: m.push_mailbox_failed_body({}, options)
			};
		case 'job_failed':
			return {
				title: m.push_job_failed_title({}, options),
				body: m.push_job_failed_body({}, options)
			};
		default:
			return { title: m.push_test_title({}, options), body: m.push_test_body({}, options) };
	}
}
