// How the build splits the app's code (Rolldown's `codeSplitting`, the client only). By itself it
// puts every module that a different set of pages uses in a chunk of its own; each icon the app
// imports (`@lucide/svelte/icons/…`) became a file of under 2 KB, nearly half of the small files a
// page loaded at first. They go in one chunk, which every page loads once (WP-05,
// .knowledge/plans/audit-frontend-fixes-5.md). The icons of the icon picker stay files of their
// own, loaded when shown: they are not `$initial` (`lib/icons/lucide.ts`).
//
// Grouping the small modules of the app itself the same way broke the start of the app (the
// order in which modules run); the messages grouped by page gave no fewer files.

/** The module of one Lucide icon. */
export const ICON = /[\\/]@lucide[\\/]svelte[\\/]dist[\\/]icons[\\/]/;

/** @returns {{ groups: { name: string; test: RegExp; tags: '$initial'[] }[] }} */
export function codeSplitting() {
	return { groups: [{ name: 'icons', test: ICON, tags: ['$initial'] }] };
}
