import { describe, expect, it } from 'vitest';
import {
	History,
	addPages,
	markOf,
	moveTo,
	partRanges,
	partsOf,
	partsRequest,
	remove,
	requestPlaces,
	sourcesOn,
	splitOff,
	startStack,
	toggleCut,
	turn,
	unchanged,
	type Stack
} from './page-edit.ts';

const six = () => startStack(6, (page) => `p${page}`);
const keys = (...pages: number[]) => new Set(pages.map((page) => `0:${page}`));
const order = (stack: Stack) => stack.map((page) => page.page);
const cuts = (stack: Stack) => stack.flatMap((page, index) => (page.cut ? [index] : []));

describe('page-edit', () => {
	it('starts with the original, which is no change', () => {
		const stack = six();
		expect(order(stack)).toEqual([1, 2, 3, 4, 5, 6]);
		expect(stack[2].image).toBe('p3');
		expect(unchanged(stack, 6)).toBe(true);
		expect(unchanged(turn(stack, keys(2), 90), 6)).toBe(false);
		expect(unchanged(toggleCut(stack, 2), 6)).toBe(false);
		expect(unchanged(remove(stack, keys(6)), 6)).toBe(false);
	});

	it('cuts the stack into parts and names their places', () => {
		const stack = toggleCut(toggleCut(six(), 2), 4);
		expect(partsOf(stack).map(order)).toEqual([
			[1, 2],
			[3, 4],
			[5, 6]
		]);
		expect(partRanges(stack)).toEqual([
			[1, 2],
			[3, 4],
			[5, 6]
		]);
		expect(cuts(toggleCut(stack, 2))).toEqual([4]);
		expect(cuts(toggleCut(stack, 0))).toEqual([2, 4]); // the first page starts a part anyway
	});

	it('turns left and right around the circle', () => {
		const left = turn(six(), keys(1), -90);
		expect(left[0].rotate).toBe(270);
		expect(turn(left, keys(1), 90)[0].rotate).toBe(0);
	});

	it('keeps a cut where the page that started a part is removed', () => {
		const stack = remove(toggleCut(six(), 2), keys(3));
		expect(order(stack)).toEqual([1, 2, 4, 5, 6]);
		expect(cuts(stack)).toEqual([2]);
	});

	it('moves pages and puts chosen ones off as a part of their own', () => {
		expect(order(moveTo(six(), keys(5), 1))).toEqual([1, 5, 2, 3, 4, 6]);
		const off = splitOff(six(), keys(2, 4));
		expect(order(off)).toEqual([1, 3, 5, 6, 2, 4]);
		expect(cuts(off)).toEqual([4]);
		expect(order(splitOff(six(), keys(1, 2, 3, 4, 5, 6)))).toEqual([1, 2, 3, 4, 5, 6]);
	});

	it('adds the pages of a file after a page or at the end', () => {
		const after = addPages(six(), 1, ['a', 'b'], 0);
		expect(after.map((page) => page.key).slice(0, 4)).toEqual(['0:1', '1:1', '1:2', '0:2']);
		expect(addPages(six(), 2, ['c'], null).at(-1)).toMatchObject({ source: 2, page: 1 });
	});

	it('makes the request with at most the chosen part replacing the document', () => {
		const stack = turn(toggleCut(six(), 3), keys(6), 90);
		expect(partsRequest(stack, 1)).toEqual([
			{
				pages: [1, 2, 3].map((page) => ({ source: 0, page, rotate: 0 })),
				replaces: false
			},
			{
				pages: [
					{ source: 0, page: 4, rotate: 0 },
					{ source: 0, page: 5, rotate: 0 },
					{ source: 0, page: 6, rotate: 90 }
				],
				replaces: true
			}
		]);
		expect(partsRequest(stack, null).every((part) => !part.replaces)).toBe(true);
	});

	it('goes back and forth through the changes', () => {
		const history = new History(six());
		history.push(remove(history.current, keys(1)));
		history.push(remove(history.current, keys(2)));
		history.undo();
		expect(order(history.current)).toEqual([2, 3, 4, 5, 6]);
		expect(history.canRedo).toBe(true);
		history.redo();
		expect(order(history.current)).toEqual([3, 4, 5, 6]);
		history.undo();
		history.push(turn(history.current, keys(3), 90));
		expect(history.canRedo).toBe(false);
		history.undo();
		history.undo();
		expect(history.canUndo).toBe(false);
		expect(order(history.current)).toEqual([1, 2, 3, 4, 5, 6]);
	});

	it('counts the files first and the other documents after them, as the API does', () => {
		// Added in turn: a document (1), a file (2), a document (3), a file (4).
		const place = requestPlaces([false, true, false, true], new Set([1, 2, 3, 4]));
		expect([0, 1, 2, 3, 4].map(place)).toEqual([0, 3, 1, 4, 2]);
		let stack = addPages(
			startStack(1, (page) => `p${page}`),
			1,
			['b1'],
			null
		);
		stack = addPages(stack, 2, ['f1'], 0);
		expect(partsRequest(stack, 0, place)[0].pages.map((pick) => pick.source)).toEqual([0, 1, 3]);
		expect([0, 1, 25, 26].map(markOf)).toEqual(['A', 'B', 'Z', '27']);
	});

	it('leaves out what has no page on the stack: undone, or every page removed', () => {
		// Added in turn: a document (1, undone), a file (2), a document (3).
		const stack = addPages(
			startStack(1, (page) => `p${page}`),
			3,
			['c1'],
			null
		);
		const used = sourcesOn(addPages(stack, 2, ['f1'], null));
		expect([...used]).toEqual([3, 2]);
		const place = requestPlaces([false, true, false], used);
		expect([0, 2, 3].map(place)).toEqual([0, 1, 2]);
		expect([...sourcesOn(startStack(2, (page) => `p${page}`))]).toEqual([]);
	});
});
