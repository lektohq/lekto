/**
 * The signed-in user, in memory only. The session cookie is HTTP-only and never visible here; the
 * CSRF token comes from `GET /auth/me` or the sign-in answer and is lost on reload, when
 * `load()` fetches it again.
 */
import { api } from '#lib/api/client.ts';
import { apiError, ApiError } from '#lib/api/problem.ts';
import { setSessionHooks } from '#lib/api/fetch.ts';
import type { components } from '#lib/api/schema.ts';

export type User = components['schemas']['UserOut'];
type SessionOut = components['schemas']['SessionOut'];
type Me = components['schemas']['Me'];

class Session {
	user = $state<User | null>(null);
	/** The version of Lekto that answers, from `GET /auth/me`; shown in the account's menu. */
	version = $state<string | null>(null);
	/** The link of the shortcut for iPhone, iPad and Mac (`LEKTO_SHORTCUT_URL`); null: the server
	 * offers none, and the web UI shows nothing of it. */
	shortcutUrl = $state<string | null>(null);
	#csrf: string | null = null;
	/** The user this tab last knew; kept when the session ends, since another person may sign in
	 * next. */
	#known: string | null = null;
	#another = false;

	/** Whether the user who signed in is another one than this tab knew before. What the tab
	 * still holds in memory (the way back to a list, values it looked up) is not theirs: the
	 * sign-in page then starts the app afresh. */
	get another(): boolean {
		return this.#another;
	}

	get isAdmin(): boolean {
		return this.user?.role === 'admin';
	}

	get csrfToken(): string | null {
		return this.#csrf;
	}

	/**
	 * Who is signed in, from the server; false without a session. Called when the app starts and
	 * whenever it asks anew (`recheckSession`): the user object is replaced only when something
	 * about the user changed, so that effects reading `session.user` (the event stream, the
	 * uploads) do not run again for nothing. Only the API's own "no session" (401) ends the
	 * session here: any other failure (a proxy answering 502 while Lekto restarts) leaves user and
	 * token as they are and is thrown, like no answer at all.
	 */
	async load(): Promise<Me | null> {
		const { data, error, response } = await api.GET('/api/v1/auth/me');
		if (data) {
			if (JSON.stringify(this.user) !== JSON.stringify(data.user)) this.user = data.user;
			this.#known = data.user.id;
			this.#csrf = data.csrf_token;
			this.version = data.lekto_version;
			this.shortcutUrl = data.shortcut_url;
			return data;
		}
		if (response.status !== 401) throw await apiError(response, error);
		this.clear();
		return null;
	}

	/** Take over a new session (sign-in answer). */
	start(signedIn: SessionOut): void {
		this.#another = this.#known !== null && this.#known !== signedIn.user.id;
		this.#known = signedIn.user.id;
		this.user = signedIn.user;
		this.#csrf = signedIn.csrf_token;
	}

	clear(): void {
		this.user = null;
		this.version = null;
		this.shortcutUrl = null;
		this.#csrf = null;
	}

	/** Sign out on the server, then forget the session; also when the server says it has gone.
	 * While the server did not sign out (no answer, a 502 of a proxy) the session stays: the
	 * cookie still holds, and the app must not look signed out. */
	async logout(): Promise<void> {
		const { error, response } = await api.POST('/api/v1/auth/logout');
		if (!response.ok && response.status !== 401) throw await apiError(response, error);
		this.clear();
	}
}

export const session = new Session();

export interface SessionEvents {
	/** The session ended or never existed: sign in again. */
	unauthorized(): void;
	/** Another sign-in in this browser (another tab) replaced the session: start afresh. */
	replaced(): void;
}

let connected: SessionEvents | null = null;
let rechecking: Promise<void> | null = null;

/**
 * Ask the server anew who is signed in. All tabs of a browser share the session cookie: someone
 * may have signed out in another tab, and another person signed in. The app asks when the tab
 * comes to the front again and when the event stream reconnects (the API closes a stream whose
 * session ended). Another user than before: start afresh (`replaced`); no session any more: sign
 * in again (`unauthorized`); the same user with another role or name: the app follows. Without
 * an answer nothing changes; the next occasion asks again.
 */
export function recheckSession(): Promise<void> {
	rechecking ??= (async () => {
		const before = session.user?.id ?? null;
		try {
			const signedIn = await session.load();
			if (before === null) return;
			if (!signedIn) connected?.unauthorized();
			else if (session.user?.id !== before) connected?.replaced();
		} catch {
			// The API is not reachable right now.
		} finally {
			rechecking = null;
		}
	})();
	return rechecking;
}

/** Connect the API client to the session. */
export function connectSession({ unauthorized, replaced }: SessionEvents): void {
	connected = { unauthorized, replaced };
	setSessionHooks({
		csrfToken: () => session.csrfToken,
		refreshCsrfToken: async () => {
			const before = session.user?.id ?? null;
			try {
				if (!(await session.load())) return null;
			} catch (error) {
				if (error instanceof ApiError) return null;
				throw error;
			}
			// The cookie is shared by all tabs: never repeat a change as someone else.
			if (before === null || session.user?.id !== before) {
				if (before !== null) replaced();
				return null;
			}
			return session.csrfToken;
		},
		unauthorized: () => {
			session.clear();
			unauthorized();
		}
	});
}
