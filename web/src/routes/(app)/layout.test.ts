// The frame of the signed-in app: what it asks when it starts.
import { render } from '@testing-library/svelte';
import { createRawSnippet } from 'svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { events } from '#lib/events.svelte.ts';
import { inbox } from '#lib/inbox.svelte.ts';
import { session } from '#lib/session.svelte.ts';
import { calls, fakeApi, masterData } from '#lib/testing/api.ts';
import { streamEvents } from '#lib/testing/events.ts';
import { summaryOf } from '#lib/testing/documents.ts';
import { goTo } from '#lib/testing/page-state.svelte.ts';
import { signIn } from '#lib/testing/session.ts';
import Layout from './+layout.svelte';
import { elapse, fakeTime } from '#lib/testing/time.ts';

vi.mock('$app/navigation', () => import('#lib/testing/navigation.ts'));
vi.mock('$app/state', () => import('#lib/testing/app-state.ts'));

afterEach(() => {
	events.stop();
	inbox.stop();
	session.clear();
});

describe('the app frame', () => {
	it('counts the inbox once when it starts, not twice (WF-K06)', async () => {
		streamEvents();
		signIn('user', { id: 'u1', username: 'jane' });
		goTo('/ui/inbox');
		const api = fakeApi(
			{ ...masterData(), 'GET /api/v1/inbox/summary': () => summaryOf() },
			() => ({})
		);
		vi.stubGlobal('fetch', api);
		fakeTime(); // a refresh the counter puts off would fall due: it passes at once
		render(Layout, { children: createRawSnippet(() => ({ render: () => '<p>Seite</p>' })) });
		await elapse(5000);
		expect(calls(api).filter((call) => call === 'GET /api/v1/inbox/summary')).toHaveLength(1);
	});
});
