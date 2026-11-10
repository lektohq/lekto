/**
 * The stack of pages in the dialog "PDF bearbeiten" (web/DESIGN.md, "Page tile"; the API's
 * `POST /documents/{id}/edit`): the pages of the document's original and of added files in
 * their order, each turned or not, and where the stack is cut into parts. Every change makes
 * a new stack, so that undoing is going back to an earlier one (`History`).
 */

export type Turn = 0 | 90 | 180 | 270;

/** One page on the stack. `source` 0 is the document's original, 1, 2, … the added files. */
export interface StackPage {
	/** Unique on the stack, for the list's keys and the choice. */
	key: string;
	source: number;
	page: number;
	rotate: Turn;
	/** A new part starts with this page (ignored for the first). */
	cut: boolean;
	/** Its image: the document's page image, or a `data:` URL of an added file's page. */
	image: string;
}

export type Stack = readonly StackPage[];

/** The parts of the request, each its pages; `replaces` the one that replaces the document. */
export interface PartRequest {
	pages: { source: number; page: number; rotate: Turn }[];
	replaces: boolean;
}

/** The document's own pages, unturned and uncut. */
export function startStack(count: number, image: (page: number) => string): StackPage[] {
	return Array.from({ length: count }, (_, index) => ({
		key: `0:${index + 1}`,
		source: 0,
		page: index + 1,
		rotate: 0 as Turn,
		cut: false,
		image: image(index + 1)
	}));
}

/** The stack split at its cuts. */
export function partsOf(stack: Stack): StackPage[][] {
	const parts: StackPage[][] = [];
	stack.forEach((page, index) => {
		if (index === 0 || page.cut) parts.push([]);
		parts[parts.length - 1].push(page);
	});
	return parts;
}

/** Whether the stack is still the original, as it came: nothing to apply. */
export function unchanged(stack: Stack, count: number): boolean {
	return (
		stack.length === count &&
		stack.every(
			(page, index) =>
				page.source === 0 &&
				page.page === index + 1 &&
				page.rotate === 0 &&
				(index === 0 || !page.cut)
		)
	);
}

/** `pages` turned by `by` degrees (clockwise; -90 turns left). */
export function turn(stack: Stack, keys: ReadonlySet<string>, by: 90 | -90): StackPage[] {
	return stack.map((page) =>
		keys.has(page.key) ? { ...page, rotate: ((page.rotate + by + 360) % 360) as Turn } : page
	);
}

/** The stack without `keys`: where a removed page started a part, the page after it does. */
export function remove(stack: Stack, keys: ReadonlySet<string>): StackPage[] {
	const kept: StackPage[] = [];
	let cut = false;
	for (const page of stack) {
		if (keys.has(page.key)) {
			cut ||= page.cut;
			continue;
		}
		kept.push(cut ? { ...page, cut: true } : page);
		cut = false;
	}
	return kept;
}

/** The pages of `keys` taken out and put, in their order, before the page at `index` of the
 * rest (at the end for the rest's length); they start no part, and the first of them where
 * `cut` says so. */
export function moveTo(stack: Stack, keys: ReadonlySet<string>, index: number, cut = false) {
	const moved = stack.filter((page) => keys.has(page.key)).map((page) => ({ ...page, cut: false }));
	const rest = remove(stack, keys);
	const at = Math.max(0, Math.min(index, rest.length));
	if (moved.length > 0 && cut) moved[0] = { ...moved[0], cut: true };
	return [...rest.slice(0, at), ...moved, ...rest.slice(at)];
}

/** The pages of `keys` as a part of their own at the end ("Als neues Dokument"). */
export function splitOff(stack: Stack, keys: ReadonlySet<string>): StackPage[] {
	const rest = stack.filter((page) => !keys.has(page.key));
	if (rest.length === 0) return [...stack];
	return moveTo(stack, keys, rest.length, true);
}

/** Cut before the page at `index` (a new part starts there), or join it to the part before. */
export function toggleCut(stack: Stack, index: number): StackPage[] {
	return stack.map((page, at) => (at === index && at > 0 ? { ...page, cut: !page.cut } : page));
}

/** The pages of the added file `source` put after the page at `after` (at the end for null). */
export function addPages(
	stack: Stack,
	source: number,
	images: readonly string[],
	after: number | null
): StackPage[] {
	const added = images.map((image, index) => ({
		key: `${source}:${index + 1}`,
		source,
		page: index + 1,
		rotate: 0 as Turn,
		cut: false,
		image
	}));
	const at = after === null ? stack.length : after + 1;
	return [...stack.slice(0, at), ...added, ...stack.slice(at)];
}

/** The parts as the API takes them; `replacing`: the index of the part that replaces the
 * document, null for none (the document is deleted). */
export function partsRequest(stack: Stack, replacing: number | null): PartRequest[] {
	return partsOf(stack).map((part, index) => ({
		pages: part.map(({ source, page, rotate }) => ({ source, page, rotate })),
		replaces: index === replacing
	}));
}

/** The first and last place (from 1) of each part on the stack. */
export function partRanges(stack: Stack): [number, number][] {
	let start = 1;
	return partsOf(stack).map((part) => {
		const range: [number, number] = [start, start + part.length - 1];
		start += part.length;
		return range;
	});
}

/** Earlier stacks to go back to, and those undone to go forward to again. */
export class History {
	#past: Stack[] = [];
	#future: Stack[] = [];

	constructor(public current: Stack) {}

	get canUndo(): boolean {
		return this.#past.length > 0;
	}

	get canRedo(): boolean {
		return this.#future.length > 0;
	}

	/** A change: the stack before it can be gone back to. */
	push(next: Stack): void {
		this.#past.push(this.current);
		this.#future = [];
		this.current = next;
	}

	undo(): void {
		const previous = this.#past.pop();
		if (previous === undefined) return;
		this.#future.push(this.current);
		this.current = previous;
	}

	redo(): void {
		const next = this.#future.pop();
		if (next === undefined) return;
		this.#past.push(this.current);
		this.current = next;
	}
}
