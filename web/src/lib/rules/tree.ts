/**
 * The tree of conditions every kind of rule has (Tobi, 05.11.2026: one model for all rules): a
 * group of all (and) or any (or), turned around or not, whose items are conditions or groups
 * again. What a condition is belongs to the kind (a document rule's `ConditionNode`, a mail
 * rule's `MailConditionNode`); the tree, its keys, its form in the API and its text are shared.
 */
import { m } from '#lib/paraglide/messages.js';

export type Mode = 'all' | 'any';

/** A condition of any kind: what the tree needs of it. */
export interface TreeCondition {
	kind: 'condition';
	key: string;
}

export interface TreeGroup<C extends TreeCondition> {
	kind: 'group';
	key: string;
	mode: Mode;
	negate: boolean;
	items: (C | TreeGroup<C>)[];
}

/** The tree as the API has it: `{"all": [...], "not": true}`; a condition has a `field`. */
export type ApiTree<A> =
	{ all: (A | ApiTree<A>)[]; not?: boolean } | { any: (A | ApiTree<A>)[]; not?: boolean };

/** The limits of every rule's tree (`lekto.core.domain.condition_tree`). */
export const TREE_LIMITS = { depth: 5, conditions: 50 } as const;

let counter = 0;
/** A key for a node of the editor, unique on the page. */
export const nextKey = (): string => `t${++counter}`;

export function newGroup<C extends TreeCondition>(
	mode: Mode = 'all',
	items: (C | TreeGroup<C>)[] = []
): TreeGroup<C> {
	return { kind: 'group', key: nextKey(), mode, negate: false, items };
}

export function treeFromApi<A extends { field: unknown }, C extends TreeCondition>(
	group: ApiTree<A>,
	condition: (item: A) => C
): TreeGroup<C> {
	const mode: Mode = 'all' in group ? 'all' : 'any';
	const items = 'all' in group ? group.all : group.any;
	return {
		kind: 'group',
		key: nextKey(),
		mode,
		negate: group.not ?? false,
		items: items.map((item) =>
			isApiCondition(item) ? condition(item) : treeFromApi(item, condition)
		)
	};
}

function isApiCondition<A extends { field: unknown }>(item: A | ApiTree<A>): item is A {
	return 'field' in item;
}

export function treeToApi<C extends TreeCondition, A>(
	group: TreeGroup<C>,
	condition: (item: C) => A
): ApiTree<A> {
	const items = group.items.map((item) =>
		item.kind === 'group' ? treeToApi(item as TreeGroup<C>, condition) : condition(item as C)
	);
	return group.mode === 'all'
		? { all: items, not: group.negate }
		: { any: items, not: group.negate };
}

/** All conditions, depth first. */
export function conditionsOf<C extends TreeCondition>(group: TreeGroup<C>): C[] {
	return group.items.flatMap((item) =>
		item.kind === 'group' ? conditionsOf(item as TreeGroup<C>) : [item as C]
	);
}

/** 1 for a group without subgroups. */
export function depthOf<C extends TreeCondition>(group: TreeGroup<C>): number {
	return (
		1 +
		Math.max(
			0,
			...group.items.map((item) => (item.kind === 'group' ? depthOf(item as TreeGroup<C>) : 0))
		)
	);
}

/** The level of a group in the tree, 1 for the root; 0 if it is not in it. */
export function levelOf<C extends TreeCondition>(
	root: TreeGroup<C>,
	key: string,
	level = 1
): number {
	if (root.key === key) return level;
	for (const item of root.items) {
		if (item.kind !== 'group') continue;
		const found = levelOf(item as TreeGroup<C>, key, level + 1);
		if (found) return found;
	}
	return 0;
}

/** The empty groups of the tree; the root counts only with `root`. */
export function emptyGroups<C extends TreeCondition>(
	group: TreeGroup<C>,
	root = true
): TreeGroup<C>[] {
	const own = root && group.items.length === 0 ? [group] : [];
	return [
		...own,
		...group.items.flatMap((item) =>
			item.kind === 'group' ? emptyGroups(item as TreeGroup<C>) : []
		)
	];
}

/** Move the item at `index` one place up (-1) or down (+1). */
export function move<T>(items: T[], index: number, by: -1 | 1): void {
	const target = index + by;
	if (target < 0 || target >= items.length) return;
	[items[index], items[target]] = [items[target], items[index]];
}

/** The heading of a group as a rule's page shows it ("Alle davon", "Keine davon"). */
export function groupHeading(group: { mode: Mode; negate: boolean }): string {
	if (group.mode === 'all') return group.negate ? m.rule_group_not_all() : m.rule_group_all();
	return group.negate ? m.rule_group_not_any() : m.rule_group_any();
}

/** The tree in one line: "A und (B oder C)", a group turned around as "nicht (…)". */
export function treeText<C extends TreeCondition>(
	group: TreeGroup<C>,
	describe: (condition: C) => string,
	inner = false
): string {
	const parts = group.items.map((item) =>
		item.kind === 'group' ? treeText(item as TreeGroup<C>, describe, true) : describe(item as C)
	);
	const text = parts.join(group.mode === 'all' ? m.rule_and() : m.rule_or());
	if (group.negate) return m.rule_not_text({ text });
	return inner && parts.length > 1 ? `(${text})` : text;
}
