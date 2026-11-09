/** A fake of the REST API for tests: JSON answers, a router by `METHOD /path`, the calls made. */
import { vi } from 'vitest';

/** A JSON answer; from 400 on a problem (`application/problem+json`), as the API sends it. */
export function json(body: unknown, status = 200): Response {
	return new Response(JSON.stringify(body), {
		status,
		headers: { 'content-type': status < 400 ? 'application/json' : 'application/problem+json' }
	});
}

type Answer = unknown | Response | Promise<unknown | Response>;
type Route = (request: Request, url: URL) => Answer;

/**
 * A fetch that answers by `METHOD /path` (`GET /api/v1/inbox`): JSON of what the route returns,
 * or its response. Without a route a GET answers an empty list (the master data), anything
 * else 204. Stub it with `vi.stubGlobal('fetch', …)`.
 */
export function fakeApi(routes: Record<string, Route> = {}) {
	return vi.fn(async (request: Request) => {
		const url = new URL(request.url);
		const route = routes[`${request.method} ${url.pathname}`];
		if (!route) return request.method === 'GET' ? json([]) : new Response(null, { status: 204 });
		const answer = await route(request, url);
		return answer instanceof Response ? answer : json(answer);
	});
}

/** The requests a fake API received, as `METHOD /path?query`. */
export function calls(api: ReturnType<typeof fakeApi>): string[] {
	return api.mock.calls.map(([request]) => {
		const url = new URL(request.url);
		return `${request.method} ${url.pathname}${url.search}`;
	});
}
