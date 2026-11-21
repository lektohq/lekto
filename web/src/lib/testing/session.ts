import type { components } from '#lib/api/schema.ts';
import { session } from '#lib/session.svelte.ts';

type Role = components['schemas']['SessionOut']['user']['role'];

/**
 * Signs a user in for a test, as the answer of a sign-in with a password does: John Doe with the
 * role, or the user with this id and name where a test tells users apart. `session.clear()`
 * signs out.
 */
export function signIn(role: Role = 'user', who: { id?: string; username?: string } = {}): void {
	session.start({
		user: { id: who.id ?? 'u1', username: who.username ?? 'john', role },
		method: 'password',
		expires_at: '2026-10-18T12:00:00Z',
		csrf_token: 'token'
	});
}
