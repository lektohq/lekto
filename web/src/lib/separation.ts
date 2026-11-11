/**
 * What the separation step (`separate`) said, for its rows and its drawing (web/DESIGN.md,
 * "Fassung"; Tobi, 11.11.2026): the codes it looked for and found, the stack cut into parts at
 * its sheets and where the parts went; for a part of a stack, where it came from; or why it did
 * not look.
 */
import { count, list, object, text } from '#lib/signals.ts';

type Json = Record<string, unknown>;

/** A code read on a page: its format, and whether it is a separator sheet's. */
export interface CodeRead {
	page: number;
	format: string;
	separator: boolean;
}

export type Separation =
	| {
			kind: 'looked';
			pages: number;
			sheets: number[];
			separators: string[];
			codes: CodeRead[];
			/** The version the first part became; null where nothing was split. */
			version: number | null;
			/** The documents the other parts became, in order. */
			splitOff: string[];
	  }
	| {
			kind: 'part';
			from: string | null;
			title: string;
			/** Its pages in the stack. */
			pages: number[];
			sheets: number[];
			stackPages: number;
	  }
	| { kind: 'split'; from: string | null; title: string }
	| { kind: 'new_version'; version: number | null; how: string | null }
	| { kind: 'off' | 'mail' | 'migration' };

const numbers = (value: unknown): number[] =>
	list(value).filter((item): item is number => typeof item === 'number');

/** What an entry of the step said; null where it does not say (an entry of another node). */
export function separationOf(value: unknown): Separation | null {
	const output = object(value);
	const why = text(output.not_looked);
	if (why === 'part')
		return {
			kind: 'part',
			from: text(output.from),
			title: text(output.title) ?? '',
			pages: numbers(output.pages),
			sheets: numbers(output.sheets),
			stackPages: count(output.stack_pages)
		};
	if (why === 'split')
		return { kind: 'split', from: text(output.from), title: text(output.title) ?? '' };
	if (why === 'new_version')
		return {
			kind: 'new_version',
			version: typeof output.version === 'number' ? output.version : null,
			how: text(output.kind)
		};
	if (why === 'off' || why === 'mail' || why === 'migration') return { kind: why };
	if (!Array.isArray(output.sheets)) return null;
	return {
		kind: 'looked',
		pages: count(output.pages),
		sheets: numbers(output.sheets),
		separators: list(output.separators).flatMap((item) => (typeof item === 'string' ? [item] : [])),
		codes: list(output.codes).flatMap((item): CodeRead[] => {
			const code = object(item as Json);
			const format = text(code.format);
			return typeof code.page === 'number' && format
				? [{ page: code.page, format, separator: code.separator === true }]
				: [];
		}),
		version: typeof output.version === 'number' ? output.version : null,
		splitOff: list(output.split_off).flatMap((item) => (typeof item === 'string' ? [item] : []))
	};
}

/** The pages of each part of a stack of `pages` pages split at `sheets`, which are left out; no
 * part is empty (as the backend splits, `domain.separating`). */
export function partsOf(pages: number, sheets: readonly number[]): number[][] {
	const parts: number[][] = [];
	let current: number[] = [];
	for (let page = 1; page <= pages; page += 1) {
		if (sheets.includes(page)) {
			if (current.length > 0) parts.push(current);
			current = [];
		} else current.push(page);
	}
	if (current.length > 0) parts.push(current);
	return parts;
}

/** A run of the stack's pages as drawn: a part (numbered from 1) or separator sheets. */
export type PageGroup = { part: number; pages: number[] } | { part: null; pages: number[] };

/** The stack's pages in order, a group for each part and each run of sheets. */
export function pageGroups(pages: number, sheets: readonly number[]): PageGroup[] {
	const groups: PageGroup[] = [];
	let part = 0;
	for (let page = 1; page <= pages; page += 1) {
		const sheet = sheets.includes(page);
		const last = groups.at(-1);
		if (last && (last.part === null) === sheet) last.pages.push(page);
		else if (sheet) groups.push({ part: null, pages: [page] });
		else {
			part += 1;
			groups.push({ part, pages: [page] });
		}
	}
	return groups;
}

/** Which part of its stack a part is (from 1), and of how many; null where its pages do not
 * make one. */
export function partNumber(
	pages: readonly number[],
	sheets: readonly number[],
	stackPages: number
): { part: number; parts: number } | null {
	const parts = partsOf(stackPages, sheets);
	const index = parts.findIndex((part) => part.length > 0 && part[0] === pages[0]);
	return index < 0 ? null : { part: index + 1, parts: parts.length };
}
