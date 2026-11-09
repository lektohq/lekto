/** The longest name of a token the API takes (`tests/api-limits.test.ts`). */
export const TOKEN_NAME_MAX = 100;

/** A token was created or revoked: the cards of the tab API-Tokens load their lists anew. */
export const tokenChanges = $state({ version: 0 });

export function tokensChanged(): void {
	tokenChanges.version++;
}
