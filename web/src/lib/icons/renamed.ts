/**
 * The names of Lucide icons that Lucide renamed after lucide 1.52, with the name each has now: a
 * contact or document type may still carry the old one, which Lucide keeps only as an alias of
 * the new. The picker offers the new names; loading takes either.
 */
export const RENAMED: Readonly<Record<string, string>> = {
	'archive-restore': 'archive-arrow-up',
	'badge-alert': 'badge-exclamation-point',
	'battery-warning': 'battery-exclamation-point',
	bold: 'letter-b',
	'book-alert': 'book-exclamation-point',
	'circle-alert': 'circle-exclamation-point',
	'circle-arrow-out-down-left': 'circle-arrow-down-left-exit',
	'circle-arrow-out-down-right': 'circle-arrow-down-right-exit',
	'circle-arrow-out-up-left': 'circle-arrow-up-left-exit',
	'circle-arrow-out-up-right': 'circle-arrow-up-right-exit',
	'circle-parking': 'circle-letter-p',
	'circle-parking-off': 'circle-letter-p-off',
	'clock-alert': 'clock-exclamation-point',
	'cloud-alert': 'cloud-exclamation-point',
	copyright: 'circle-letter-c',
	heading: 'letter-h',
	'mail-warning': 'mail-exclamation-point',
	'message-circle-warning': 'message-circle-exclamation-point',
	'message-square-warning': 'message-square-exclamation-point',
	music: 'eighth-notes',
	'music-2': 'eighth-note',
	'music-3': 'half-note',
	'music-4': 'sixteenth-notes',
	'octagon-alert': 'octagon-exclamation-point',
	'search-alert': 'search-exclamation-point',
	'shield-alert': 'shield-exclamation-point',
	'square-arrow-out-down-left': 'square-arrow-down-left-exit',
	'square-arrow-out-down-right': 'square-arrow-down-right-exit',
	'square-arrow-out-up-left': 'square-arrow-up-left-exit',
	'square-arrow-out-up-right': 'square-arrow-up-right-exit',
	'square-m': 'square-letter-m',
	'square-parking': 'square-letter-p',
	'square-parking-off': 'square-letter-p-off',
	'triangle-alert': 'triangle-exclamation-point'
};

/** The name Lucide gives the icon `name` now. */
export function currentName(name: string): string {
	return Object.hasOwn(RENAMED, name) ? RENAMED[name] : name;
}
