/**
 * The head of a list that stays while it scrolls (web/DESIGN.md, "Sticky heads"): below the
 * header (`HEADER`, 64 px) stands one line, the tools of the documents list from the desktop on,
 * their row below it. That row steps aside while the page scrolls down and comes back as soon as
 * it scrolls up (`aside`); it only steps aside once it stands at the top, and a few pixels
 * either way (`SLACK`) change nothing, so that a finger resting on the glass does not shake it.
 */

/** The height of the app's header (`AppShell`, `h-16`): what sticks stands below it. */
export const HEADER = 64;

/** How far the page moves against the last turn before the row follows. */
export const SLACK = 6;

/** Whether the row stands aside, and where the page last turned. */
export interface Aside {
	hidden: boolean;
	anchor: number;
}

/** The row's state after the page scrolled to `y`; `stuck`: it stands at the top. */
export function aside(state: Aside, y: number, stuck: boolean): Aside {
	if (!stuck) return { hidden: false, anchor: y };
	if (state.hidden) {
		return y < state.anchor - SLACK
			? { hidden: false, anchor: y }
			: { hidden: true, anchor: Math.max(state.anchor, y) };
	}
	return y > state.anchor + SLACK
		? { hidden: true, anchor: y }
		: { hidden: false, anchor: Math.min(state.anchor, y) };
}
