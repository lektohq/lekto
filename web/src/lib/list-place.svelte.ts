/**
 * The place in a list one comes back to (web/DESIGN.md, "Navigation between list and detail").
 * The lists load in the page, after it is shown: SvelteKit restores the scroll position while
 * the list is still empty and lands at its top. So the page keeps its place itself, in its
 * `snapshot` (the back button) and in the history entry of the way back (`page.state.place`,
 * the link "Dokumente" of a document), and goes there once the list has loaded.
 */
import { tick } from 'svelte';

/** Where one stood in a list: how far down, and how many items a list that loads more showed. */
export interface Place {
	y: number;
	loaded?: number;
}

export class ListPlace {
	/** The place to come back to; null: none, or reached. */
	wanted = $state<Place | null>(null);

	/** Come back to `place` once the list has loaded; anything else than a place is none (a
	 * history entry may be older than this version). */
	want(place: unknown): void {
		if (typeof place !== 'object' || place === null) return;
		const { y, loaded } = place as { y?: unknown; loaded?: unknown };
		if (typeof y !== 'number' || !Number.isFinite(y)) return;
		this.wanted = { y, loaded: typeof loaded === 'number' ? loaded : undefined };
	}

	/** The list stands as it loaded: go to the place wanted, once. */
	async reach(): Promise<void> {
		const place = this.wanted;
		if (!place) return;
		this.wanted = null;
		await tick();
		window.scrollTo(0, place.y);
	}
}
