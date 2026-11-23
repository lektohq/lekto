/**
 * The room the bars of a page take that stick to its top and bottom (the header, the tools of
 * the documents, a selection bar). The browser scrolls what the keyboard reaches just into
 * view, which is under such a bar: the focus is there and cannot be seen (WCAG 2.4.11). So the
 * page tells how much room they take, and the document scrolls a target clear of it
 * (`scroll-padding` in `app.css`, from `--clear-top` and `--clear-bottom`).
 */

type Edge = 'top' | 'bottom';

const taken: Record<Edge, Map<symbol, number>> = { top: new Map(), bottom: new Map() };

function write(edge: Edge): void {
	const most = Math.max(0, ...taken[edge].values());
	const root = document.documentElement;
	// Without anything of a page the header alone counts (the default of `app.css`).
	if (most > 0) root.style.setProperty(`--clear-${edge}`, `${Math.round(most)}px`);
	else root.style.removeProperty(`--clear-${edge}`);
}

/**
 * Keep `pixels` at an edge of the window clear of what the keyboard reaches, measured from that
 * edge to the inner end of the bar. Several bars may say so: the largest counts. Returns the
 * function that takes it back.
 */
export function keepClear(edge: Edge, pixels: number): () => void {
	const key = Symbol(edge);
	taken[edge].set(key, pixels);
	write(edge);
	return () => {
		taken[edge].delete(key);
		write(edge);
	};
}
