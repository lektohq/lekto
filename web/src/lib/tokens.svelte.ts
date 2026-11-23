import { unwrap } from '#lib/api/call.ts';
import { api } from '#lib/api/client.ts';
import type { components } from '#lib/api/schema.ts';
import { session } from '#lib/session.svelte.ts';

type Token = components['schemas']['TokenOut'];

/** The longest name of a token the API takes (`tests/api-limits.test.ts`). */
export const TOKEN_NAME_MAX = 100;

/** A token was created or revoked: the cards of the tab API-Tokens load their lists anew. */
export const tokenChanges = $state({ version: 0 });

export function tokensChanged(): void {
	tokenChanges.version++;
}

/**
 * The caller's API tokens, read once for everything that shows them or asks whether one
 * exists: the list of the tab API-Tokens, the shortcut's card beside it, the hint of the upload
 * dialog. Read again after a change (`tokensChanged`) and for another user.
 */
class Tokens {
	/** Null until read, and when the read failed. */
	list = $state<Token[] | null>(null);
	/** Why the last read failed; null when it did not. */
	failure = $state<unknown>(null);
	#read: string | null = null;
	#reading: Promise<void> = Promise.resolve();

	/** Read the list, unless it is read (or on its way) for this user and this state of the
	 * tokens; `again` reads it in any case ("Erneut versuchen"). Called in an effect, it runs
	 * again after a change. */
	load(again = false): Promise<void> {
		const wanted = `${session.user?.id ?? ''}:${tokenChanges.version}`;
		if (!again && this.#read === wanted) return this.#reading;
		this.#read = wanted;
		this.#reading = unwrap(api.GET('/api/v1/auth/tokens')).then(
			(list) => {
				if (this.#read === wanted) [this.list, this.failure] = [list, null];
			},
			(failure: unknown) => {
				if (this.#read === wanted) [this.list, this.failure] = [null, failure];
			}
		);
		return this.#reading;
	}

	/** Whether a token that only uploads exists (the shortcut is set up); null while that is
	 * not known: not read yet, or the read failed. */
	get hasUploadToken(): boolean | null {
		return this.list?.some((token) => token.scope === 'upload') ?? null;
	}
}

export const tokens = new Tokens();
