// What a page shows in the console while a spec drives it: an error is a finding, unless it is
// an answer the test instance gives on purpose, known by its address (WT2-10). Before, any
// 4xx or 5xx passed: a page whose request failed counted as working.
import type { Page } from '@playwright/test';

/** A request that fails on purpose: its address, and why. */
export type Expected = { url: RegExp; why: string };

/** Requests that fail on purpose in every test instance. */
const EXPECTED: Expected[] = [
	{ url: /\/api\/v1\/auth\/me$/, why: 'asking who is signed in before anyone is (401)' },
	// The test instances (README.md, the CI job `layout`) run without Meilisearch.
	{ url: /\/api\/v1\/search\/status$/, why: 'no search configured (503)' }
];

/** The problems of `page`: errors in its console and errors it throws; `also` the failures a
 * spec brings about itself. */
export function watch(page: Page, also: Expected[] = []): string[] {
	const problems: string[] = [];
	page.on('console', (message) => {
		if (message.type() !== 'error') return;
		const { url } = message.location();
		const failed = /status of [45]\d\d/.test(message.text());
		if (failed && [...EXPECTED, ...also].some((known) => known.url.test(url))) return;
		problems.push(failed ? `${message.text()}: ${url}` : message.text());
	});
	page.on('pageerror', (error) => problems.push(error.message));
	return problems;
}
