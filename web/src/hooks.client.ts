import type { HandleClientError } from '@sveltejs/kit/hooks';
import { describeError, isNetworkError } from '#lib/errors.ts';

// An error while a page loads (API unreachable, 503): the error page shows it in the user's
// language and with the API's detail, not SvelteKit's "Internal Error". Without an answer at
// all it may be offline (web/DESIGN.md, "App").
export const handleError: HandleClientError = ({ error }) => ({
	message: describeError(error),
	offline: isNetworkError(error)
});
