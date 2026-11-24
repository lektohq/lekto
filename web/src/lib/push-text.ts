import { formatNumber } from '#lib/i18n.ts';
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

/** The data of a push (`event.data`), or the test notification's words where it has none or
 * none that is JSON: every push must show a notification (iPhone and iPad). */
export function pushPayload(data: { json(): unknown } | null, base: string): PushPayload {
	try {
		const payload = data?.json();
		if (payload && typeof payload === 'object') return payload as PushPayload;
	} catch {
		// no JSON: the test notification below
	}
	return { kind: 'test', params: {}, url: `${base}/`, badge: null, tag: null, locale: 'en' };
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
					: m.push_waiting_many({ count: formatNumber(waiting) }, options);
			const body = titles.length
				? titles.join(' · ')
				: fresh > 1
					? m.push_waiting_new({ count: formatNumber(fresh) }, options)
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
