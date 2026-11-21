import type { HandleClientError } from '@sveltejs/kit/hooks';
import { describeError, isGatewayError, isNetworkError } from '#lib/errors.ts';

// An error while a page loads (API unreachable, 503): the error page shows it in the user's
// language and with the API's detail, not SvelteKit's "Internal Error". Without an answer at
// all it may be offline (web/DESIGN.md, "App"). Without an answer of Lekto, the device online
// (the server restarts, a proxy answers for it), the error page asks again by itself.
export const handleError: HandleClientError = ({ error }) => ({
	message: describeError(error),
	offline: isNetworkError(error),
	unreachable: isNetworkError(error) || isGatewayError(error)
});
