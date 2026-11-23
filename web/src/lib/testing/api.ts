/** A fake of the REST API for tests: JSON answers, a router by `METHOD /path`, the calls made. */
import { vi } from 'vitest';
import type { components } from '#lib/api/schema.ts';

type Schemas = components['schemas'];
type Problem = Schemas['Problem'];
type ReasonCode = Schemas['ReasonCode'];

/** A JSON answer; from 400 on a problem (`application/problem+json`), as the API sends it. */
export function json(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
	return new Response(JSON.stringify(body), {
		status,
		headers: {
			'content-type': status < 400 ? 'application/json' : 'application/problem+json',
			...headers
		}
	});
}

/** The titles the API gives its problems (`PROBLEMS` in `adapters/inbound/problems.py`). */
const TITLES: Record<number, string> = {
	400: 'Bad Request',
	401: 'Unauthorized',
	403: 'Forbidden',
	404: 'Not Found',
	405: 'Method Not Allowed',
	409: 'Conflict',
	413: 'Content Too Large',
	415: 'Unsupported Media Type',
	422: 'Unprocessable Content',
	429: 'Too Many Requests',
	500: 'Internal Server Error',
	501: 'Not Implemented',
	502: 'Bad Gateway',
	503: 'Service Unavailable'
};

/** One part of a request that does not fit (a 422 of the request): its place, its code. */
export type InputError = {
	field: string;
	code: ReasonCode;
	params?: Record<string, unknown>;
	message?: string;
};

/** What a problem says beyond its status, as the API fills it. */
export type ProblemParts = {
	/** The English text; without one, the title (as an `HTTPException` of the API has it); null
	 * for none at all. */
	detail?: string | null;
	/** The reason of an error of the core, which the UI translates. */
	code?: ReasonCode;
	params?: Record<string, unknown>;
	/** A request that does not fit: each part with its reason; `detail` joins their texts. */
	errors?: InputError[];
} & Partial<
	Pick<
		Problem,
		| 'existing_document_id'
		| 'space_id'
		| 'open_fields'
		| 'blocking_spaces'
		| 'second_factor_required'
	>
>;

/**
 * A problem as the API builds it (`problems.py`): its title by the status, the English
 * `detail`, `reason` with code and parameters for an error of the core, `errors` for a request
 * that does not fit. What it does not say is null, as the type has it.
 */
export function problemOf(status: number, parts: ProblemParts = {}): Problem {
	const { detail, code, params = {}, errors, ...extra } = parts;
	const inputs = errors?.map(({ field, code, params = {}, message = code }) => ({
		field,
		message,
		reason: { code, params }
	}));
	return {
		type: 'about:blank',
		title: TITLES[status] ?? String(status),
		status,
		detail:
			detail === undefined
				? (inputs?.map((each) => `${each.field}: ${each.message}`).join('; ') ??
					TITLES[status] ??
					null)
				: detail,
		existing_document_id: null,
		space_id: null,
		open_fields: null,
		blocking_spaces: null,
		second_factor_required: null,
		reason: code === undefined ? null : { code, params },
		errors: inputs ?? null,
		...extra
	};
}

/** The answer with a problem, as the API sends it: what is null left out. */
export function problem(
	status: number,
	parts: ProblemParts = {},
	headers: Record<string, string> = {}
): Response {
	const sent = Object.fromEntries(
		Object.entries(problemOf(status, parts)).filter(([, value]) => value !== null)
	);
	return json(sent, status, headers);
}

/** An answer without a body (204), as the API gives one to a change that returns nothing. */
export function noContent(): Response {
	return new Response(null, { status: 204 });
}

/** A PDF as the API sends a document's file. */
export function pdf(): Response {
	return new Response(new Uint8Array([37, 80, 68, 70]), {
		headers: { 'content-type': 'application/pdf' }
	});
}

/** What the API answers for something that is not there, or not for the caller (`NotFoundError`
 * of the core): `kind` as the core names it (`document`, `document type`, `mailbox`). */
export function notFound(kind: string, id: string): Response {
	return problem(404, {
		detail: `${kind} ${id} not found`,
		code: 'not_found',
		params: { kind, id }
	});
}

type Answer = unknown | Response | Promise<unknown | Response>;
/** The answer of a fake API to one request: JSON of what it returns, or its response. */
export type Route = (request: Request, url: URL) => Answer;
/** The routes of a fake API, by `METHOD /path`. */
export type Routes = Record<string, Route>;

/** A request a test reads back: method, path, its JSON body (null without one). */
export type Sent = { method: string; path: string; body: unknown };

/** `routes`, each request kept in `sent` before it is answered. */
export function recording(routes: Routes, sent: Sent[]): Routes {
	return Object.fromEntries(
		Object.entries(routes).map(([key, route]) => [
			key,
			async (request: Request, url: URL) => {
				const body = await request
					.clone()
					.json()
					.catch(() => null);
				sent.push({ method: request.method, path: url.pathname, body });
				return route(request, url);
			}
		])
	);
}

/** The lists of master data a page reads (`loadLookup`, `loadRuleLookup`), by their path. */
type MasterData =
	'contacts' | 'document-types' | 'tags' | 'fields' | 'spaces' | 'users' | 'webhooks' | 'mailboxes';

/**
 * The routes of the master data a page reads, each list empty unless given
 * (`fakeApi({ ...masterData({ tags: [tag] }), … })`).
 */
export function masterData(given: Partial<Record<MasterData, unknown[]>> = {}): Routes {
	const lists: MasterData[] = [
		'contacts',
		'document-types',
		'tags',
		'fields',
		'spaces',
		'users',
		'webhooks',
		'mailboxes'
	];
	return Object.fromEntries(lists.map((list) => [`GET /api/v1/${list}`, () => given[list] ?? []]));
}

/** The requests a fake answered without a route, since `tests/setup.ts` last asked. */
const unrouted: string[] = [];

/** The requests a fake answered without a route since the last call; `tests/setup.ts` fails
 * the test that made one. */
export function takeUnrouted(): string[] {
	return unrouted.splice(0);
}

/**
 * A fetch that answers by `METHOD /path` (`GET /api/v1/inbox`): JSON of what the route returns,
 * or its response. Without a route `otherwise` answers, if given; else nothing does: the
 * request gets a 501 and fails the test (`tests/setup.ts`), so a wrong path or method never
 * passes on a plausible answer. Stub it with `vi.stubGlobal('fetch', …)`.
 */
export function fakeApi(routes: Routes = {}, otherwise?: Route) {
	return vi.fn(async (request: Request) => {
		const url = new URL(request.url);
		const route = routes[`${request.method} ${url.pathname}`] ?? otherwise;
		if (!route) {
			unrouted.push(`${request.method} ${url.pathname}`);
			return problem(501, {
				detail: `the fake has no route for ${request.method} ${url.pathname}`
			});
		}
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
