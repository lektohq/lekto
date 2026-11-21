import { toast } from 'svelte-sonner';
import { ApiError } from '#lib/api/problem.ts';
import { m } from '#lib/paraglide/messages.js';
import { type Reason, reasonsText } from '#lib/reasons.ts';

/** A refusal the API reported within an answer of 200 (one decision of several): its reason. */
export class ReasonError extends Error {
	constructor(readonly reason: Reason) {
		super(reason.code);
	}
}

/** A text for the user about a failed call: the problem's reason in the user's language where
 * the API gave one with a code this UI knows, else the detail as the API wrote it. */
export function describeError(error: unknown): string {
	if (error instanceof ApiError) {
		if (error.status === 429) {
			return error.retryAfter !== null
				? m.error_too_many({ seconds: error.retryAfter })
				: m.error_too_many_later();
		}
		if (isGatewayError(error)) return m.error_network();
		const problem = error.problem;
		const detail = problem?.reason
			? reasonsText([problem.reason], problem.detail)
			: (problem?.detail ?? null);
		if (error.status === 403)
			return detail ? `${m.error_forbidden()} ${detail}` : m.error_forbidden();
		return detail ?? error.problem?.title ?? m.error_unexpected({ status: error.status });
	}
	if (error instanceof ReasonError) {
		return reasonsText([error.reason], null) ?? m.error_unexpected({ status: 200 });
	}
	// fetch rejects with a TypeError when the server cannot be reached.
	if (error instanceof TypeError) return m.error_network();
	return m.error_unexpected({ status: 0 });
}

/** Whether a call failed because no answer came at all (no connection, the server down):
 * `fetch` rejects with a TypeError then, worded by each browser its own way. */
export function isNetworkError(error: unknown): boolean {
	return error instanceof TypeError && /fetch|network|load failed/i.test(error.message);
}

/** Whether the answer came from a proxy in front of a Lekto that is not there (it restarts
 * after an update), not from Lekto: a 5xx without the API's problem details. Lekto's own
 * failure always carries them (a 500 as much as a 503 for a search that is missing), a proxy's
 * is text or nothing (502, 503, 504, and Traefik's plain 500 while its service is empty). To
 * the person that is the same as no answer: the server cannot be reached. */
export function isGatewayError(error: unknown): boolean {
	return error instanceof ApiError && error.status >= 500 && error.problem === null;
}

/** Whether a failed call may succeed when asked again: no answer at all, or a failure of the
 * server itself (5xx: it restarts, a proxy answers for it). What the API refuses (403, 404,
 * 422) it refuses again. Who follows something that runs asks on after the first, and stops
 * at the second. */
export function isPassing(error: unknown): boolean {
	return isNetworkError(error) || (error instanceof ApiError && error.status >= 500);
}

/** Show a failed call as a toast. */
export function reportError(error: unknown): void {
	toast.error(describeError(error));
}

/**
 * The messages of a 422 by field (`fields.<id>` of the API as `field:<id>`): each part's reason
 * in the user's language (`errors` of the problem), or, from an API without them, the details
 * as it writes them (`field: message; field: message`); anything else stays out of the result.
 */
export function fieldErrors(error: unknown): Record<string, string> {
	const found: Record<string, string> = {};
	if (!(error instanceof ApiError) || error.status !== 422) return found;
	const parts = error.problem?.errors;
	if (parts?.length) {
		for (const part of parts) {
			const name = part.field.replace(/^fields\./, 'field:');
			found[name] = reasonsText([part.reason], part.message) ?? part.message;
		}
		return found;
	}
	for (const part of (error.problem?.detail ?? '').split('; ')) {
		const match = /^([\w-]+(?:\.[\w-]+)*): (.+)$/.exec(part);
		if (!match) continue;
		const name = match[1].replace(/^fields\./, 'field:');
		found[name] = match[2];
	}
	return found;
}
