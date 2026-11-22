/** Builders for tests of what an admin sets up and watches, in the form the API sends it:
 * mailboxes, webhooks, the jobs. */
import type { components } from '#lib/api/schema.ts';

type Schemas = components['schemas'];
type Mailbox = Schemas['MailboxOut'];
type Webhook = Schemas['WebhookOut'];
type JobsSummary = Schemas['JobsSummaryOut'];
type KindSummary = Schemas['KindSummaryOut'];

const SET_UP = '2026-11-04T10:00:00Z';

/** The household's mailbox `m1`: the inbox every five minutes, nothing fetched yet. */
export function mailboxOf(
	overrides: Omit<Partial<Mailbox>, 'status'> & { status?: Partial<Mailbox['status']> } = {}
): Mailbox {
	const { status, ...rest } = overrides;
	return {
		id: 'm1',
		name: 'Haushalt',
		host: 'imap.example.test',
		port: 993,
		security: 'tls',
		username: 'haushalt@example.test',
		folders: ['INBOX'],
		interval_minutes: 5,
		start: 'since_setup',
		since: null,
		fallback: 'nothing',
		fallback_user_id: null,
		body_type_id: null,
		enabled: true,
		created_at: SET_UP,
		updated_at: SET_UP,
		...rest,
		status: {
			last_attempt_at: null,
			last_success_at: null,
			error: null,
			mails: 0,
			documents: 0,
			skipped_at: null,
			skipped: null,
			step_failed_at: null,
			step_failed: null,
			keywords: [],
			own_keywords: null,
			...status
		}
	};
}

/** The webhook `hook` of u1: every event, signed, a thin body, working. */
export function webhookOf(overrides: Partial<Webhook> = {}): Webhook {
	return {
		id: 'hook',
		owner_id: 'u1',
		name: 'Test',
		url: 'https://node.example/lekto',
		event_types: ['*'],
		active: true,
		signed: true,
		headers: [],
		body: 'thin',
		body_template: null,
		max_open_tasks: 4,
		model_call: null,
		disabled_reason: null,
		disabled_reasons: [],
		failed_streak: 0,
		previous_secret_valid_until: null,
		created_at: '2026-10-25T10:00:00Z',
		updated_at: '2026-10-25T10:00:00Z',
		...overrides
	};
}

/** The jobs of each kind, the counts not given 0, as of 24.10.2026 12:00. */
export function jobsSummaryOf(
	kinds: Record<string, Partial<Omit<KindSummary, 'kind'>>>,
	overrides: Partial<JobsSummary> = {}
): JobsSummary {
	return {
		kinds: Object.entries(kinds).map(([kind, counts]) => ({
			kind,
			running: 0,
			due: 0,
			planned: 0,
			failed: 0,
			done: 0,
			...counts
		})),
		last_started_at: '2026-10-24T11:59:58Z',
		now: '2026-10-24T12:00:00Z',
		kept_since: '2026-10-17T12:00:00Z',
		...overrides
	};
}
