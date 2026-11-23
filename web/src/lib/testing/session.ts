import type { components } from '#lib/api/schema.ts';
import { session } from '#lib/session.svelte.ts';

type Role = components['schemas']['SessionOut']['user']['role'];
type Me = components['schemas']['Me'];

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

/** The answer of `GET /api/v1/auth/me` for a session with a password: John Doe as a user, no
 * second factor, no link of the shortcut. */
export function meOf(overrides: Partial<Me> = {}): Me {
	return {
		user: { id: 'u1', username: 'john', role: 'user' },
		authenticated_with: 'session',
		csrf_token: 'token',
		session_expires_at: '2026-10-18T12:00:00Z',
		token_scope: null,
		rights: [],
		has_password: true,
		totp_enabled: false,
		linked_accounts: [],
		lekto_version: '0.8.0',
		api_version: '0.5',
		instance_id: 'instance-1',
		shortcut_url: null,
		...overrides
	};
}
