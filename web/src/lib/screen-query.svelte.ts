/**
 * Whether a media query of the window holds, for markup that differs in structure (where only
 * looks differ, CSS decides): `desktop` and `phone`. Tests choose with `override`.
 */
import { MediaQuery } from 'svelte/reactivity';

export class ScreenQuery {
	#query: MediaQuery | null = null;
	#override = $state<boolean | null>(null);

	constructor(readonly media: string) {}

	get current(): boolean {
		if (this.#override !== null) return this.#override;
		this.#query ??= new MediaQuery(this.media);
		return this.#query.current;
	}

	/** For tests: it holds (true), it does not (false), or the window again (null). */
	override(value: boolean | null): void {
		this.#override = value;
	}
}
