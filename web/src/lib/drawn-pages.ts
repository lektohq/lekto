/**
 * Which pages of a long PDF stay drawn (`PdfViewer`). A page is drawn when it comes near the
 * view, and its canvas holds every pixel of it: one page up to 64 MB after a zoom. Keeping
 * every page ever shown cost a 40-page document 2.6 GB in the browser, and Safari on a phone
 * leaves canvases blank beyond its limit. So only the pages near the view and the last few
 * beside them stay, as pdf.js's own viewer keeps them (its `DEFAULT_CACHE_SIZE` is 10); a
 * page that comes back is drawn again.
 */

/** Pages kept drawn, those near the view among them. */
export const KEPT_PAGES = 10;

export class DrawnPages<T> {
	#keep: number;
	#near = new Set<number>();
	/** The drawn pages, the one drawn or looked at longest ago first. */
	#drawn = new Map<number, T>();

	constructor(keep: number = KEPT_PAGES) {
		this.#keep = keep;
	}

	/** How many pages are drawn. */
	get size(): number {
		return this.#drawn.size;
	}

	/** The page came near the view: it is not let go while it is there, and counts as looked
	 * at now. */
	show(number: number): void {
		this.#near.add(number);
		const held = this.#drawn.get(number);
		if (held === undefined) return;
		this.#drawn.delete(number);
		this.#drawn.set(number, held);
	}

	/** The page left the view. */
	hide(number: number): void {
		this.#near.delete(number);
	}

	/** The page was drawn on `canvas`. Returns the pages to let go, with theirs: the ones
	 * looked at longest ago beyond what is kept, never one near the view. */
	drew(number: number, canvas: T): [number, T][] {
		this.#drawn.delete(number);
		this.#drawn.set(number, canvas);
		const gone: [number, T][] = [];
		for (const [other, held] of this.#drawn) {
			if (this.#drawn.size - gone.length <= this.#keep) break;
			if (this.#near.has(other) || other === number) continue;
			gone.push([other, held]);
		}
		for (const [other] of gone) this.#drawn.delete(other);
		return gone;
	}

	/** The page is no longer drawn (its drawing was cancelled, or it went with the viewer). */
	drop(number: number): void {
		this.#drawn.delete(number);
	}
}
