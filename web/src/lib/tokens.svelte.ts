/** A token was created or revoked: the cards of the tab API-Tokens load their lists anew. */
export const tokenChanges = $state({ version: 0 });

export function tokensChanged(): void {
	tokenChanges.version++;
}
