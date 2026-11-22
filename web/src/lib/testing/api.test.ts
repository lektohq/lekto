import { describe, expect, it } from 'vitest';
import { fakeApi, masterData, notFound, problem, takeUnrouted } from './api.ts';

describe('the fake API of the tests', () => {
	it('answers nothing it has no route for, and tells the setup so (WT1-05)', async () => {
		// A wrong path or method got an empty list or a 204 and passed for a plausible answer.
		const api = fakeApi({ 'GET /api/v1/tags': () => [] });
		expect((await api(new Request('http://lekto/api/v1/tags'))).status).toBe(200);
		const wrong = await api(new Request('http://lekto/api/v1/tags', { method: 'POST' }));
		expect(wrong.status).toBe(501);
		expect((await api(new Request('http://lekto/api/v1/tag'))).status).toBe(501);
		// Taken here, so this test does not fail for them.
		expect(takeUnrouted()).toEqual(['POST /api/v1/tags', 'GET /api/v1/tag']);
		expect(takeUnrouted()).toEqual([]);
	});

	it('routes the master data a page reads, each empty unless given', async () => {
		const api = fakeApi(masterData({ tags: [{ id: 't1' }] }));
		const read = async (path: string) =>
			(await api(new Request(`http://lekto/api/v1/${path}`))).json();
		expect(await read('tags')).toEqual([{ id: 't1' }]);
		expect(await read('document-types')).toEqual([]);
	});

	it('builds a problem as the API sends it: no null, the reason with its code', async () => {
		expect(await notFound('mailbox', 'm1').json()).toEqual({
			type: 'about:blank',
			title: 'Not Found',
			status: 404,
			detail: 'mailbox m1 not found',
			reason: { code: 'not_found', params: { kind: 'mailbox', id: 'm1' } }
		});
		const refused = problem(422, {
			errors: [{ field: 'name', code: 'input_too_long', params: { max: 200 }, message: 'long' }]
		});
		expect(refused.headers.get('content-type')).toBe('application/problem+json');
		expect(await refused.json()).toMatchObject({
			detail: 'name: long',
			errors: [{ field: 'name', message: 'long', reason: { code: 'input_too_long' } }]
		});
	});
});
