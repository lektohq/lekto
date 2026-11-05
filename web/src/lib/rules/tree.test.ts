import { describe, expect, it } from 'vitest';
import {
	conditionsOf,
	depthOf,
	emptyGroups,
	isGroup,
	levelOf,
	move,
	newGroup,
	treeFromApi,
	treeToApi,
	type TreeCondition,
	type TreeGroup
} from './tree.ts';

interface Leaf extends TreeCondition {
	field: string;
}

const leaf = (field: string): Leaf => ({ kind: 'condition', key: field, field });
type ApiLeaf = { field: string };

function sample(): TreeGroup<Leaf> {
	return newGroup('all', [
		leaf('a'),
		newGroup('any', [leaf('b'), newGroup('all', [leaf('c')])]),
		newGroup('any', [])
	]);
}

describe('the tree of conditions every rule has', () => {
	it('tells groups from conditions and walks them depth first', () => {
		const tree = sample();
		expect(isGroup(tree.items[0])).toBe(false);
		expect(isGroup(tree.items[1])).toBe(true);
		expect(conditionsOf(tree).map((item) => item.field)).toEqual(['a', 'b', 'c']);
		expect(depthOf(tree)).toBe(3);
		expect(levelOf(tree, tree.key)).toBe(1);
		const inner = (tree.items[1] as TreeGroup<Leaf>).items[1] as TreeGroup<Leaf>;
		expect(levelOf(tree, inner.key)).toBe(3);
	});

	it('finds the empty groups, the root only when asked', () => {
		const tree = sample();
		expect(emptyGroups(tree).map((group) => group.key)).toEqual([tree.items[2].key]);
		const root = newGroup<Leaf>('all', []);
		expect(emptyGroups(root)).toHaveLength(1);
		expect(emptyGroups(root, false)).toHaveLength(0);
	});

	it('goes to the API and back unchanged, with "not" on every group', () => {
		const api = {
			all: [{ field: 'a' }, { any: [{ field: 'b' }], not: true }],
			not: false
		};
		const tree = treeFromApi<ApiLeaf, Leaf>(api, (item) => leaf(item.field));
		expect(tree.items).toHaveLength(2);
		expect((tree.items[1] as TreeGroup<Leaf>).negate).toBe(true);
		expect(treeToApi(tree, (item): ApiLeaf => ({ field: item.field }))).toEqual(api);
	});

	it('moves an item one place, and stays at the ends', () => {
		const items = ['a', 'b', 'c'];
		move(items, 0, 1);
		expect(items).toEqual(['b', 'a', 'c']);
		move(items, 0, -1);
		expect(items).toEqual(['b', 'a', 'c']);
		move(items, 2, 1);
		expect(items).toEqual(['b', 'a', 'c']);
	});
});
