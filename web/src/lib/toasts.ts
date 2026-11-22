/**
 * Toasts above a dialog or a sheet (web/DESIGN.md, "Alerts"). An open layer takes the pointer
 * from everything outside it, and a tap outside closes it. A toast is outside, and it may wait
 * for an answer (a new version of the app): it takes the pointer back (`TOAST_CLASS`), and a
 * tap on it is none on the page behind the layer (`inToast`).
 */

/** The classes of every toast: the look, and reachable above an open layer. */
export const TOAST_CLASS = 'cn-toast pointer-events-auto';

/** The ✕ of a toast, 20 px as svelte-sonner draws it: reachable as every target, 24 px with
 * a mouse and a finger's 44 px on a phone ("Touch targets"). */
export const TOAST_CLOSE_CLASS = 'after:absolute after:-inset-0.5 max-sm:after:-inset-3';

/** Whether `target` lies in a toast. */
export function inToast(target: EventTarget | null): boolean {
	return target instanceof Element && target.closest('[data-sonner-toaster]') !== null;
}
