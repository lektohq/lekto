import { describe, expect, it } from 'vitest';
import { pageGroups, partNumber, partsOf, separationOf } from '#lib/separation.ts';

describe('separationOf', () => {
	it('reads what the step found in a stack', () => {
		expect(
			separationOf({
				sheets: [5],
				pages: 8,
				separators: ['PATCHT'],
				codes: [
					{ page: 1, format: 'QR Code', separator: false },
					{ page: 5, format: 'Code 128', separator: true }
				],
				parts: 2,
				version: 2,
				split_off: ['b']
			})
		).toEqual({
			kind: 'looked',
			pages: 8,
			sheets: [5],
			separators: ['PATCHT'],
			codes: [
				{ page: 1, format: 'QR Code', separator: false },
				{ page: 5, format: 'Code 128', separator: true }
			],
			version: 2,
			splitOff: ['b']
		});
	});

	it('reads a part of a stack, pages split off by hand and why it did not look', () => {
		expect(
			separationOf({
				not_looked: 'part',
				from: 'a',
				title: 'scan',
				pages: [6, 7, 8],
				sheets: [5],
				stack_pages: 8
			})
		).toEqual({
			kind: 'part',
			from: 'a',
			title: 'scan',
			pages: [6, 7, 8],
			sheets: [5],
			stackPages: 8
		});
		expect(separationOf({ not_looked: 'split', from: 'a', title: 'scan' })).toEqual({
			kind: 'split',
			from: 'a',
			title: 'scan'
		});
		expect(separationOf({ not_looked: 'new_version', version: 3, kind: 'edited' })).toEqual({
			kind: 'new_version',
			version: 3,
			how: 'edited'
		});
		expect(separationOf({ not_looked: 'mail' })).toEqual({ kind: 'mail' });
		expect(separationOf({ not_looked: 'too_long', pages: 412, max: 200 })).toEqual({
			kind: 'too_long',
			pages: 412,
			max: 200
		});
	});

	it('says nothing where the entry does not tell', () => {
		expect(separationOf({})).toBeNull();
		expect(separationOf({ not_looked: 'unknown' })).toBeNull();
	});
});

describe('the parts of a stack', () => {
	it('leaves the sheets out and no part empty, as the backend splits', () => {
		expect(partsOf(8, [3, 6])).toEqual([
			[1, 2],
			[4, 5],
			[7, 8]
		]);
		expect(partsOf(6, [1, 3, 4, 6])).toEqual([[2], [5]]);
		expect(partsOf(2, [1, 2])).toEqual([]);
	});

	it('groups the pages into parts and runs of sheets', () => {
		expect(pageGroups(8, [5])).toEqual([
			{ part: 1, pages: [1, 2, 3, 4] },
			{ part: null, pages: [5] },
			{ part: 2, pages: [6, 7, 8] }
		]);
		expect(pageGroups(5, [1, 3, 4])).toEqual([
			{ part: null, pages: [1] },
			{ part: 1, pages: [2] },
			{ part: null, pages: [3, 4] },
			{ part: 2, pages: [5] }
		]);
	});

	it('tells which part of its stack a part is', () => {
		expect(partNumber([6, 7, 8], [5], 8)).toEqual({ part: 2, parts: 2 });
		expect(partNumber([1, 2], [3, 6], 8)).toEqual({ part: 1, parts: 3 });
		expect(partNumber([9], [5], 8)).toBeNull();
	});
});
