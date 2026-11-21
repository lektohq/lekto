import { describe, expect, it } from 'vitest';
import { DrawnPages, KEPT_PAGES } from './drawn-pages.ts';

describe('the pages of a PDF that stay drawn (WC-05)', () => {
	it('lets go of the page looked at longest ago, beyond what is kept', () => {
		// Every page ever shown stayed drawn: 40 pages held 2.6 GB.
		const pages = new DrawnPages<string>(3);
		const gone: number[] = [];
		for (let number = 1; number <= 6; number++) {
			pages.show(number);
			gone.push(...pages.drew(number, `canvas ${number}`).map(([page]) => page));
			pages.hide(number);
		}
		expect(gone).toEqual([1, 2, 3]);
		expect(pages.size).toBe(3);
	});

	it('gives the canvas of each page it lets go, to be emptied', () => {
		const pages = new DrawnPages<string>(1);
		pages.drew(1, 'first');
		expect(pages.drew(2, 'second')).toEqual([[1, 'first']]);
	});

	it('never lets go of a page near the view, however many there are', () => {
		const pages = new DrawnPages<string>(2);
		for (const number of [1, 2, 3, 4]) pages.show(number);
		const gone = [1, 2, 3, 4].flatMap((number) => pages.drew(number, 'c'));
		expect(gone).toEqual([]);
		expect(pages.size).toBe(4);
		// Scrolled on: the first two left the view, the next page takes their place.
		pages.hide(1);
		pages.hide(2);
		pages.show(5);
		expect(pages.drew(5, 'c').map(([page]) => page)).toEqual([1, 2]);
	});

	it('counts a page looked at again as the newest', () => {
		const pages = new DrawnPages<string>(2);
		pages.drew(1, 'c');
		pages.drew(2, 'c');
		pages.show(1); // scrolled back to it
		pages.hide(1);
		expect(pages.drew(3, 'c').map(([page]) => page)).toEqual([2]);
	});

	it('keeps as many as the viewer of pdf.js', () => {
		expect(KEPT_PAGES).toBe(10);
		const pages = new DrawnPages<string>();
		const gone = Array.from({ length: 40 }, (_, index) => pages.drew(index + 1, 'c')).flat();
		expect([pages.size, gone.length]).toEqual([10, 30]);
	});
});
