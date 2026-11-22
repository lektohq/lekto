// The tab "Classifier": the latest model, the next training, the accuracy over the models and
// the hit rate of each signal; training on request for admins.
import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { events } from '#lib/events.svelte.ts';
import { signIn } from '#lib/testing/session.ts';
import { m } from '#lib/paraglide/messages.js';
import { session } from '#lib/session.svelte.ts';
import Page from './ClassifierTab.svelte';
import { fakeApi, problem, type Route, type Routes } from '#lib/testing/api.ts';

let fetchMock: ReturnType<typeof fakeApi>;

const trained = {
	model: {
		number: 2,
		trained_at: '2026-10-13T12:00:00Z',
		examples: 1515,
		examples_until: '2026-10-13T11:00:00Z',
		classes: { contact: 80, document_type: 16, topic: 4, space: 3, tags: 9 },
		learned_identifiers: 42,
		accuracy: { tested: 303, contact: 0.91, document_type: 0.87 },
		method: 'scikit-learn 1.9.1 lekto-tfidf-logreg/1'
	},
	confirmed: 1520,
	since: 5,
	min_examples: 20,
	retrain_after: 25,
	threshold: 0.8
};

const models = [
	{
		...trained.model,
		number: 1,
		examples: 900,
		accuracy: { tested: 180, contact: 0.8, document_type: 0.7 }
	},
	trained.model
];

const signals = {
	channels: ['api', 'web'],
	period: '12m',
	since: '2025-11-01T00:00:00Z',
	signals: [
		{ field: 'contact', signal: 'signal_llm', hits: 2, misses: 1, decided: 4 },
		{ field: 'contact', signal: 'signal_facts', hits: 1, misses: 0, decided: 4 },
		{ field: 'document_date', signal: 'signal_llm', hits: 3, misses: 1, decided: 4 }
	]
};

/** The classifier's endpoints, `status` its status; `more` before these. */
function serve(status: Route = () => trained, more: Routes = {}) {
	fetchMock = fakeApi({
		'GET /api/v1/classifier': status,
		'GET /api/v1/classifier/models': () => models,
		'GET /api/v1/automation/signals': () => signals,
		'POST /api/v1/classifier/train': () => new Response(null, { status: 202 }),
		...more
	});
	vi.stubGlobal('fetch', fetchMock);
}

beforeEach(() => {
	signIn('admin', { id: 'admin', username: 'admin' });
	serve();
});

afterEach(() => {
	session.clear();
});

describe('the classifier tab', () => {
	it('shows what the model learned and trains on request', async () => {
		render(Page);
		expect(
			await screen.findByRole('heading', { name: m.classifier_model_title({ number: 2 }) })
		).toBeTruthy();
		expect(screen.getByText(m.classifier_class_identifiers())).toBeTruthy();
		expect(screen.getByText('42')).toBeTruthy();
		expect(screen.getByText(m.classifier_next_of({ needed: '25' }))).toBeTruthy();
		expect(screen.getByText(m.classifier_next_text({ number: 2 }))).toBeTruthy();
		await userEvent.click(screen.getByRole('button', { name: m.classifier_train() }));
		const post = fetchMock.mock.calls.map((call) => call[0]).find((call) => call.method === 'POST');
		expect(new URL(post!.url).pathname).toBe('/api/v1/classifier/train');
	});

	it('shows a user the model without the training', async () => {
		signIn('user', { id: 'user', username: 'erika' });
		render(Page);
		expect(
			await screen.findByRole('heading', { name: m.classifier_model_title({ number: 2 }) })
		).toBeTruthy();
		expect(screen.queryByRole('button', { name: m.classifier_train() })).toBeNull();
	});

	it('shows the new model once a training ended', async () => {
		let emit: ((message: { data: string }) => void) | undefined;
		events.useFactory(
			() =>
				({
					addEventListener(type: string, handler: (message: { data: string }) => void) {
						if (type === 'classifier.trained') emit = handler;
					},
					close() {}
				}) as unknown as EventSource
		);
		events.start(() => {});
		let current: unknown = trained;
		serve(() => current);
		render(Page);
		expect(
			await screen.findByRole('heading', { name: m.classifier_model_title({ number: 2 }) })
		).toBeTruthy();

		current = { ...trained, model: { ...trained.model, number: 3 } };
		emit?.({
			data: JSON.stringify({ type: 'classifier.trained', id: 'e1', occurred_at: '', number: 3 })
		});
		expect(
			await screen.findByRole('heading', { name: m.classifier_model_title({ number: 3 }) })
		).toBeTruthy();
		events.stop();
	});

	it('says so when the model could not be read anew: the one shown is the old one (WE-02)', async () => {
		let emit: ((message: { data: string }) => void) | undefined;
		events.useFactory(
			() =>
				({
					addEventListener(type: string, handler: (message: { data: string }) => void) {
						if (type === 'classifier.trained') emit = handler;
					},
					close() {}
				}) as unknown as EventSource
		);
		events.start(() => {});
		let down = false;
		// Down, every endpoint fails.
		const or = (answer: unknown) => () => (down ? problem(500, { detail: 'boom' }) : answer);
		serve(or(trained), {
			'GET /api/v1/classifier/models': or(models),
			'GET /api/v1/automation/signals': or(signals)
		});
		render(Page);
		const model = () =>
			screen.getByRole('heading', { name: m.classifier_model_title({ number: 2 }) });
		await screen.findByRole('heading', { name: m.classifier_model_title({ number: 2 }) });
		down = true;
		emit?.({
			data: JSON.stringify({ type: 'classifier.trained', id: 'e1', occurred_at: '', number: 3 })
		});
		expect((await screen.findByRole('alert')).textContent).toContain('boom');
		expect(model()).toBeTruthy();
		events.stop();
	});

	it('draws the accuracy over the models', async () => {
		render(Page);
		expect(await screen.findByRole('img', { name: m.classifier_history_label() })).toBeTruthy();
		expect(screen.queryByText(m.classifier_history_none())).toBeNull();
	});

	it('tells the hit rate of each signal and marks the best', async () => {
		render(Page);
		const table = await screen.findByRole('table');
		const rows = Array.from(table.querySelectorAll('tbody tr'));
		const llm = rows.find((row) => row.textContent?.includes(m.node_signal_llm()))!;
		expect(llm.textContent).toContain(m.classifier_signal_of({ count: '3', decided: '4' }));
		expect(llm.textContent).toContain(m.classifier_signal_best()); // the date: it alone
		const facts = rows.find((row) => row.textContent?.includes(m.node_signal_facts()))!;
		expect(facts.textContent).toContain(m.classifier_signal_best()); // the contact: all hits
		expect(facts.querySelectorAll(`[aria-label="${m.classifier_signal_none()}"]`)).toHaveLength(4);
	});

	it('says so when there is no classifier', async () => {
		const missing = () => problem(503, { detail: 'no classifier is configured' });
		serve(missing, {
			'GET /api/v1/classifier/models': missing,
			'GET /api/v1/automation/signals': missing
		});
		render(Page);
		expect(await screen.findByText(m.classifier_not_configured())).toBeTruthy();
		expect(screen.queryByRole('button', { name: m.classifier_train() })).toBeNull();
	});
});
