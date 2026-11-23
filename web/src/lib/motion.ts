/**
 * Motion that code starts (web/DESIGN.md, "Motion"): a scroll to a place, the wait for a
 * transition. Who asked the system for less motion gets the place at once. CSS asks for itself
 * (`motion-safe:`); what a script moves asks here, in one place.
 */

/** Whether the person asked for less motion. */
export function reducedMotion(): boolean {
	return window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches ?? false;
}

/** How a scripted scroll moves: gliding, or at once for who asked for less motion. */
export function scrollBehavior(): ScrollBehavior {
	return reducedMotion() ? 'auto' : 'smooth';
}
