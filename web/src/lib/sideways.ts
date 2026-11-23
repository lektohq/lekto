/**
 * A row that stays one line and scrolls sideways where it is wider than its room, with a fade
 * at the cut edge (web/DESIGN.md, "Tabs and switches"): the `TabBar`, `Segmented`, a row of
 * badges (`SidewaysRow`). `sideways` marks the edges that have more behind them, `SIDEWAYS_FADE`
 * draws the fade from the marks, `centre` brings the chosen one into view.
 */
import type { Attachment } from 'svelte/attachments';

/** The fade at each edge `sideways` marks. */
export const SIDEWAYS_FADE = [
	'data-more-end:[mask-image:linear-gradient(to_right,black_85%,transparent)]',
	'data-more-start:[mask-image:linear-gradient(to_left,black_85%,transparent)]',
	'data-more-start:data-more-end:[mask-image:linear-gradient(to_right,transparent,black_15%,black_85%,transparent)]'
].join(' ');

/** Marks which edges of the row have more behind them (`data-more-start`, `data-more-end`),
 * as it scrolls and as it or what stands in it changes its size or its number. */
export const sideways: Attachment<HTMLElement> = (room) => {
	const measure = () => {
		const end = room.scrollWidth - room.clientWidth - room.scrollLeft;
		room.toggleAttribute('data-more-start', room.scrollLeft > 1);
		room.toggleAttribute('data-more-end', end > 1);
	};
	const sizes = new ResizeObserver(measure);
	const watch = () => {
		sizes.disconnect();
		sizes.observe(room);
		for (const child of room.children) sizes.observe(child);
		measure();
	};
	const children = new MutationObserver(watch);
	children.observe(room, { childList: true });
	room.addEventListener('scroll', measure, { passive: true });
	watch();
	return () => {
		sizes.disconnect();
		children.disconnect();
		room.removeEventListener('scroll', measure);
	};
};

/** Scrolls the row so that the chosen one of it (`selector`) stands in its middle. */
export function centre(room: HTMLElement | null, selector: string): void {
	const chosen = room?.querySelector<HTMLElement>(selector);
	if (!room || !chosen) return;
	room.scrollLeft = Math.max(0, chosen.offsetLeft - (room.clientWidth - chosen.offsetWidth) / 2);
	// A browser says so by itself, a moment later; the marks follow at once.
	room.dispatchEvent(new Event('scroll'));
}
