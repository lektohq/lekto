/**
 * Errors of saving a rule, next to the block they concern. The API names the place in a 422
 * (`conditions.all[1].any[0]: …`, `actions[2]: …`; request validation also names schema parts
 * in between), the missing id in a 404 (`tag <id> not found`) and the space in a 403. A 422
 * that names no place gives its reason with a code (an invalid pattern, a tag of the wrong
 * kind): it stands in the user's language, an invalid pattern at the conditions that hold it.
 */
import { ApiError } from '#lib/api/problem.ts';
import { describeError } from '#lib/errors.ts';
import { m } from '#lib/paraglide/messages.js';
import { referencedIds, type GroupNode, type RuleModel } from '#lib/rules/model.ts';
import type { TreeCondition, TreeGroup } from '#lib/rules/tree.ts';

export interface SaveErrors {
	/** Messages by key, as `validate` gives them: `name`, `priority`, `triggers`, a block's key. */
	byKey: Record<string, string>;
	/** What belongs to no block. */
	general: string | null;
}

/**
 * What the editor of a kind of rule (a document's, a mail's) tells the errors of a save about
 * its form: where the API's places lie in it. One way for every rule (web/DESIGN.md, "Mail
 * rules"), so that a refused save reads the same in both editors.
 */
export interface Places {
	/** The first parts of the places the API names for this kind of rule. */
	heads: readonly string[];
	/** The key of the block at a place, or null. */
	keyAt(path: string): string | null;
	/** Whether the schema parts on a place are the kinds of the blocks there (request
	 * validation reports one error for every kind it tried); without it every place fits. */
	fits?(path: string): boolean;
	/** The keys of the conditions that match by `pattern`. */
	matching?(pattern: string): string[];
}

/** The key of the node of `tree` at the rest of a place below `conditions`, or null. */
export function keyInTree<C extends TreeCondition>(
	rest: readonly string[],
	tree: TreeGroup<C>
): string | null {
	let node: TreeGroup<C> | C = tree;
	for (let i = 0; i < rest.length; i++) {
		if ((rest[i] === 'all' || rest[i] === 'any') && /^\d+$/.test(rest[i + 1] ?? '')) {
			if (node.kind !== 'group') return null;
			const next: TreeGroup<C> | C | undefined = node.items[Number(rest[i + 1])];
			if (!next) return null;
			node = next;
			i++;
		}
	}
	return node.key;
}

/** The key of the block at `path`, or null. */
export function keyAt(path: string, model: RuleModel): string | null {
	const [head, ...rest] = partsOf(path);
	if (head === 'name' || head === 'priority' || head === 'triggers') return head;
	if (head === 'actions') {
		const index = Number(rest[0]);
		return Number.isInteger(index) ? (model.actions[index]?.key ?? null) : 'actions';
	}
	if (head !== 'conditions') return null;
	return keyInTree(rest, model.conditions);
}

/** The places of a document rule's form. */
function rulePlaces(model: RuleModel): Places {
	return {
		heads: ['name', 'priority', 'triggers', 'scope', 'conditions', 'actions'],
		keyAt: (path) => keyAt(path, model),
		fits: (path) => fits(path, model),
		matching: (pattern) => conditionsMatching(model, pattern)
	};
}

export function saveErrors(error: unknown, model: RuleModel): SaveErrors {
	return saveErrorsAt(error, rulePlaces(model), (result) => {
		const detail = error instanceof ApiError ? (error.problem?.detail ?? '') : '';
		if (error instanceof ApiError && error.status === 404) {
			const missing = /^(.+?) ([0-9a-f-]{36}) not found$/i.exec(detail)?.[2];
			const blocks = missing ? blocksUsing(model, missing) : [];
			for (const key of blocks) result.byKey[key] = m.rule_error_missing();
			return blocks.length > 0;
		}
		if (error instanceof ApiError && error.status === 403 && error.problem?.space_id) {
			const space = model.actions.find((action) => action.type === 'set_space');
			if (space) result.byKey[space.key] = describeError(error);
			return space !== undefined;
		}
		return false;
	});
}

/**
 * The errors of a refused save at `places`: the parts of a 422 next to their blocks, what names
 * no place in the user's language, anything else as one line. `more` places what only a kind of
 * rule knows (a missing id of a 404, the space of a 403) and says whether it did.
 */
export function saveErrorsAt(
	error: unknown,
	places: Places,
	more: (result: SaveErrors) => boolean = () => false
): SaveErrors {
	const result: SaveErrors = { byKey: {}, general: null };
	const detail = error instanceof ApiError ? (error.problem?.detail ?? '') : '';
	if (error instanceof ApiError && error.status === 422 && detail) {
		const errors = partsOfDetail(detail, places);
		const reason = error.problem?.reason;
		if (reason && typeof reason.params.at === 'string') {
			placedReason(error, reason.params.at, places, result);
		} else if (reason && errors.every((part) => part.path === null)) {
			unplacedReason(error, reason, places, result);
		} else {
			byPlace(errors, places, result);
		}
		return result;
	}
	if (more(result)) return result;
	result.general = describeError(error);
	return result;
}

type DetailPart = { path: string | null; message: string };
type ProblemReason = NonNullable<NonNullable<ApiError['problem']>['reason']>;

/** The errors of a 422's detail, each with its place where it names one. "; " joins them, but
 * may stand in a message too: a part without a place continues the one before. */
function partsOfDetail(detail: string, places: Places): DetailPart[] {
	const placed = new RegExp(`^((?:${places.heads.join('|')})\\b[\\w.[\\]-]*): (.+)$`);
	const errors: DetailPart[] = [];
	for (const part of detail.split('; ')) {
		const match = placed.exec(part);
		const last = errors.at(-1);
		if (match) errors.push({ path: match[1], message: match[2] });
		else if (last) last.message += `; ${part}`;
		else errors.push({ path: null, message: part });
	}
	return errors;
}

/** A reason that names its place (`at`: a template's unknown value at "actions[0]"): in the
 * user's language at that block. */
function placedReason(error: ApiError, at: string, places: Places, result: SaveErrors): void {
	const key = places.keyAt(at);
	if (key) result.byKey[key] = describeError(error);
	else result.general = describeError(error);
}

/** No place, but a reason with a code: in the user's language, and a pattern's at the
 * conditions that match by it. */
function unplacedReason(
	error: ApiError,
	reason: ProblemReason,
	places: Places,
	result: SaveErrors
): void {
	const message = describeError(error);
	const pattern = PATTERN_CODES.has(reason.code) ? reason.params.pattern : undefined;
	const blocks = typeof pattern === 'string' ? (places.matching?.(pattern) ?? []) : [];
	for (const key of blocks) result.byKey[key] = message;
	if (blocks.length === 0) result.general = message;
}

/** Each error at its block, the rest together. Request validation tries every kind of a
 * condition or group: the kinds that are not the block's are dropped, unless nothing else is
 * left. */
function byPlace(errors: DetailPart[], places: Places, result: SaveErrors): void {
	const fitting = errors.filter(
		(error) => error.path === null || (places.fits?.(error.path) ?? true)
	);
	const rest: string[] = [];
	for (const error of fitting.length > 0 ? fitting : errors) {
		const key = error.path === null ? null : places.keyAt(error.path);
		if (key) result.byKey[key] ??= error.message;
		else rest.push(error.path === null ? error.message : `${error.path}: ${error.message}`);
	}
	result.general = rest.length > 0 ? rest.join('; ') : null;
}

/** The parts of a place: names, indexes (`all[1]`, `all.1`) and the schema parts request
 * validation puts in between (`AllGroup[ConditionSchema]`, `ConditionSchema`). */
export function partsOf(path: string): string[] {
	return path.match(/[A-Za-z_][\w-]*(?:\[[A-Za-z_][\w-]*\])?|\d+/g) ?? [];
}

/** Whether the schema parts on `path` (`AllGroup[ConditionSchema]`, `ConditionSchema`) are the
 * kinds of the blocks there; request validation reports one error for every kind it tried. */
function fits(path: string, model: RuleModel): boolean {
	const [head, ...rest] = partsOf(path);
	if (head !== 'conditions') return true;
	let node: GroupNode | RuleModel['conditions']['items'][number] = model.conditions;
	for (let i = 0; i < rest.length; i++) {
		const part = rest[i];
		const group = /^(All|Any)Group/.exec(part)?.[1]?.toLowerCase();
		if (group && (node.kind !== 'group' || node.mode !== group)) return false;
		if (/^Condition/.test(part) && node.kind === 'group') return false;
		if ((part === 'all' || part === 'any') && /^\d+$/.test(rest[i + 1] ?? '')) {
			if (node.kind !== 'group') return false;
			const next: GroupNode['items'][number] | undefined = node.items[Number(rest[i + 1])];
			if (!next) return true;
			node = next;
			i++;
		}
	}
	return true;
}

/** The reasons about a pattern (`params.pattern`). */
const PATTERN_CODES: ReadonlySet<string> = new Set(['pattern_invalid', 'pattern_too_large']);

/** The conditions that match by `pattern`. */
function conditionsMatching(model: RuleModel, pattern: string): string[] {
	const keys: string[] = [];
	const visit = (group: GroupNode) => {
		for (const item of group.items) {
			if (item.kind === 'group') visit(item);
			else if (item.op === 'matches' && item.value === pattern) keys.push(item.key);
		}
	};
	visit(model.conditions);
	return keys;
}

function blocksUsing(model: RuleModel, id: string): string[] {
	const keys: string[] = [];
	const visit = (group: GroupNode) => {
		for (const item of group.items) {
			if (item.kind === 'group') visit(item);
			else if (referencedIds(item).includes(id)) keys.push(item.key);
		}
	};
	visit(model.conditions);
	for (const action of model.actions) {
		if (referencedIds(action).includes(id)) keys.push(action.key);
	}
	return keys;
}
