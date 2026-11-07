import { redirect } from '@sveltejs/kit';
import { isNetworkError } from '#lib/errors.ts';
import { loginHref } from '#lib/navigation.ts';
import { session } from '#lib/session.svelte.ts';

// Every page here needs a signed-in user; without one, sign in and come back. Without a
// connection the app keeps the user it knows and the page says it cannot load (web/DESIGN.md,
// "App"); at a start without one the error page says so.
export async function load({ url }) {
	let signedIn: boolean;
	try {
		signedIn = await session.load();
	} catch (error) {
		if (isNetworkError(error) && session.user) return;
		throw error;
	}
	if (!signedIn) redirect(307, loginHref(url.pathname + url.search));
}
