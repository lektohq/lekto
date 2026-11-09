/**
 * Mail rules (Regeln › Mails; Tobi, 04.11.2026, mock E): what a mailbox's mails bring in. The
 * form of the editor as the API takes it, and a rule in one line for the list.
 */
import type { components } from '#lib/api/schema.ts';
import type { Space } from '#lib/masterdata.svelte.ts';
import {
	flagLabel,
	importanceLabel,
	isKeyword,
	MAIL_FIELD_LABELS,
	MAIL_FIELD_OPERATORS,
	type MailField,
	type MailOperator
} from '#lib/mail-traits.ts';
import { quoted } from '#lib/i18n.ts';
import { folderLabel } from '#lib/mailboxes.ts';
import { m } from '#lib/paraglide/messages.js';
import { mailOperatorLabel } from '#lib/rules/describe.ts';
import { DEFAULT_PRIORITY, LIMITS } from '#lib/rules/model.ts';
import {
	conditionsOf,
	emptyGroups,
	levelOf,
	newGroup,
	nextKey,
	treeFromApi,
	treeText,
	treeToApi,
	TREE_LIMITS,
	type ApiTree,
	type TreeGroup
} from '#lib/rules/tree.ts';

export type MailRule = components['schemas']['MailRuleOut'];
export type MailRuleCreate = components['schemas']['MailRuleCreate'];
export type MailRulePatch = components['schemas']['MailRulePatch'];
export type { MailField, MailOperator } from '#lib/mail-traits.ts';
export type MailParts = components['schemas']['MailParts'];
export type MailAction = components['schemas']['MailAction'];
export type DryRunMail = components['schemas']['DryRunMailOut'];
export type MailRuleDryRun = components['schemas']['MailRuleDryRun'];
type ApiCondition = components['schemas']['MailConditionBody'];

export const FIELDS: readonly MailField[] = [
	'sender',
	'recipient',
	'to',
	'cc',
	'subject',
	'folder',
	'attachments',
	'importance',
	'keyword',
	'flag'
];

/** The comparisons of each field, as the document rules' mail conditions have them. */
export const OPERATORS = MAIL_FIELD_OPERATORS;

export const PARTS: readonly MailParts[] = ['all', 'attachments', 'text', 'nothing'];
/** The steps on a mail on the server (Tobi, 05.11.2026), in the order "Aktion hinzufügen"
 * offers them; a move or the trash ends the list, once. */
export const STEP_ACTIONS: readonly MailAction[] = [
	'read',
	'unread',
	'flag',
	'unflag',
	'add_keyword',
	'remove_keyword',
	'move',
	'trash'
];
export const ENDING: readonly MailAction[] = ['move', 'trash'];
export const MAX_STEPS = 10;

export const FIELD_LABELS = MAIL_FIELD_LABELS;

/** A comparison in the words of the document rules' mail fields ("ist", "endet auf",
 * "Schlagwörter enthalten"); attachments are there or not. */
export const operatorText = mailOperatorLabel;

/** The value a condition on `field` starts with: the first of a choice, else empty. */
export function firstValue(field: MailField, folders: readonly string[]): string {
	if (field === 'folder') return folders[0] ?? '';
	if (field === 'importance') return 'high';
	return '';
}

export const PARTS_LABELS: Record<MailParts, () => string> = {
	all: m.mail_rule_parts_all,
	attachments: m.mail_rule_parts_attachments,
	text: m.mail_rule_parts_text,
	nothing: m.mail_rule_parts_nothing
};

/** A step as its row and "Aktion hinzufügen" name it ("Schlagwort hinzufügen"). */
export const STEP_LABELS: Record<MailAction, () => string> = {
	read: m.mail_step_read,
	unread: m.mail_step_unread,
	flag: m.mail_step_flag,
	unflag: m.mail_step_unflag,
	add_keyword: m.mail_step_add_keyword,
	remove_keyword: m.mail_step_remove_keyword,
	move: m.mail_step_move,
	trash: m.mail_step_trash
};

/** Whether a step names something: the flag's colour, a keyword, a folder. */
export const takesValue = (action: MailAction) =>
	action === 'flag' || action === 'add_keyword' || action === 'remove_keyword' || action === 'move';

export interface StepForm {
	key: string;
	action: MailAction;
	value: string;
}

export function newStep(action: MailAction): StepForm {
	return { key: nextKey(), action, value: action === 'flag' ? 'red' : '' };
}

/** `steps` with a new one: an ending one last, another before an ending one. */
export function withStep(steps: readonly StepForm[], action: MailAction): StepForm[] {
	const step = newStep(action);
	const end = steps.findIndex((item) => ENDING.includes(item.action));
	if (ENDING.includes(action) || end < 0) return [...steps, step];
	return [...steps.slice(0, end), step, ...steps.slice(end)];
}

/** The steps "Aktion hinzufügen" offers: one ending step at most, and those without a value
 * once. */
export function addableSteps(steps: readonly StepForm[]): MailAction[] {
	if (steps.length >= MAX_STEPS) return [];
	const ends = steps.some((item) => ENDING.includes(item.action));
	return STEP_ACTIONS.filter(
		(action) =>
			!(ENDING.includes(action) && ends) &&
			(takesValue(action) || !steps.some((item) => item.action === action))
	);
}

/** What is wrong with a step's value, in words; null where nothing is. */
function stepProblem(step: StepForm): string | null {
	const value = step.value.trim();
	switch (step.action) {
		case 'add_keyword':
		case 'remove_keyword':
			return isKeyword(value) ? null : m.mail_rule_error_keyword();
		case 'move':
		case 'flag':
			return value === '' ? m.rule_error_value() : null;
		default:
			return null;
	}
}

/** Whether the operator takes a value. */
export const hasValue = (op: MailOperator) => op !== 'present' && op !== 'missing';

/** A condition of a mail rule in the editor: a leaf of the tree every rule has. */
export interface MailConditionNode {
	kind: 'condition';
	key: string;
	field: MailField;
	op: MailOperator;
	value: string;
}
export type MailGroupNode = TreeGroup<MailConditionNode>;

/** The actions beside "Übernehmen" and "Für", each there or not (mock E: "+ Aktion"). */
export type Optional = 'space' | 'type';
export const OPTIONALS: readonly Optional[] = ['space', 'type'];

export interface MailRuleForm {
	mailboxId: string;
	name: string;
	priority: string;
	/** The root may be empty: a rule without conditions takes every mail. */
	conditions: MailGroupNode;
	parts: MailParts;
	userId: string;
	spaceId: string;
	typeId: string;
	/** On the server afterwards, in order; a move or the trash last. */
	steps: StepForm[];
	shown: Optional[];
}

export function newCondition(field: MailField = 'sender'): MailConditionNode {
	return { kind: 'condition', key: nextKey(), field, op: OPERATORS[field][0], value: '' };
}

function conditionFromApi(item: ApiCondition): MailConditionNode {
	return {
		kind: 'condition',
		key: nextKey(),
		field: item.field,
		op: item.op,
		value: item.value ?? ''
	};
}

function conditionToApi(item: MailConditionNode): ApiCondition {
	return { field: item.field, op: item.op, value: hasValue(item.op) ? item.value.trim() : null };
}

/** The tree of a stored rule's conditions; empty for one without (every mail). */
export function treeOf(rule: Pick<MailRule, 'conditions'>): MailGroupNode {
	return rule.conditions
		? treeFromApi(rule.conditions as ApiTree<ApiCondition>, conditionFromApi)
		: newGroup<MailConditionNode>('all', []);
}

export function canAddCondition(form: MailRuleForm): boolean {
	return conditionsOf(form.conditions).length < TREE_LIMITS.conditions;
}

/** A subgroup in `group` stays within the depth limit and brings a condition with it. */
export function canAddGroup(form: MailRuleForm, group: MailGroupNode): boolean {
	return canAddCondition(form) && levelOf(form.conditions, group.key) < TREE_LIMITS.depth;
}

/** The form of a stored rule, or of a new one for `mailboxId` with its mailbox's type. */
export function formOf(rule: MailRule | null, mailboxId = '', typeId = ''): MailRuleForm {
	if (!rule) {
		return {
			mailboxId,
			name: '',
			priority: String(DEFAULT_PRIORITY),
			conditions: newGroup<MailConditionNode>('all', [newCondition()]),
			parts: 'all',
			userId: '',
			spaceId: '',
			typeId,
			steps: [],
			shown: typeId ? ['type'] : []
		};
	}
	const shown: Optional[] = [];
	if (rule.space_id) shown.push('space');
	if (rule.text_type_id) shown.push('type');
	return {
		mailboxId: rule.mailbox_id,
		name: rule.name,
		priority: String(rule.priority),
		conditions: treeOf(rule),
		parts: rule.parts,
		userId: rule.user_id ?? '',
		spaceId: rule.space_id ?? '',
		typeId: rule.text_type_id ?? '',
		steps: rule.after.map((step) => ({
			key: nextKey(),
			action: step.action,
			value: step.value ?? ''
		})),
		shown
	};
}

/** The problems of the form in words, by key: `name`, `priority`, `mailbox`, `user`, and the
 * key of a condition, an empty group or a step (as the document rules' `validate`). */
export function validate(form: MailRuleForm, spaces?: readonly Space[]): Record<string, string> {
	const problems: Record<string, string> = {};
	const name = form.name.trim();
	if (name === '') problems.name = m.rule_error_name();
	else if (name.length > LIMITS.name) {
		problems.name = m.rule_error_text_long({ max: LIMITS.name });
	}
	const priority = Number(form.priority);
	if (
		!Number.isInteger(priority) ||
		priority < LIMITS.priorityMin ||
		priority > LIMITS.priorityMax
	) {
		problems.priority = m.rule_error_priority();
	}
	if (form.mailboxId === '') problems.mailbox = m.rule_error_choose();
	if (form.parts !== 'nothing' && form.userId === '') problems.user = m.rule_error_choose();
	// The space, where the spaces are known (the editor knows them; a check of the form alone does not).
	if (spaces && form.parts !== 'nothing' && form.shown.includes('space') && form.spaceId !== '') {
		const edits = spaces.some(
			(space) =>
				space.id === form.spaceId &&
				space.members.some((item) => item.user_id === form.userId && item.role === 'edit')
		);
		if (!edits) problems.space = m.rule_error_choose();
	}
	for (const group of emptyGroups(form.conditions, false)) {
		problems[group.key] = m.rule_error_group_empty();
	}
	for (const item of conditionsOf(form.conditions)) {
		if (!hasValue(item.op)) continue;
		const value = item.value.trim();
		if (item.field === 'keyword') {
			if (!isKeyword(value)) problems[item.key] = m.mail_rule_error_keyword();
		} else if (value === '') {
			problems[item.key] = m.rule_error_value();
		} else if (item.field !== 'folder' && value.length > LIMITS.text) {
			problems[item.key] = m.rule_error_text_long({ max: LIMITS.text });
		}
	}
	for (const step of form.steps) {
		const problem = stepProblem(step);
		if (problem) problems[step.key] = problem;
	}
	return problems;
}

/** Whether the form can be saved. */
export const complete = (form: MailRuleForm): boolean => Object.keys(validate(form)).length === 0;

function body(form: MailRuleForm) {
	const takes = form.parts !== 'nothing';
	return {
		name: form.name.trim(),
		priority: Number(form.priority),
		conditions: form.conditions.items.length
			? (treeToApi(form.conditions, conditionToApi) as MailRuleCreate['conditions'])
			: null,
		parts: form.parts,
		user_id: takes ? form.userId : null,
		space_id: takes && form.shown.includes('space') && form.spaceId ? form.spaceId : null,
		text_type_id: takes && form.shown.includes('type') && form.typeId ? form.typeId : null,
		after: form.steps.map((step) => ({
			action: step.action,
			value: takesValue(step.action) ? step.value.trim() : null
		}))
	};
}

/** "1 Mail", "12 Mails". */
export const mailsCount = (count: number): string =>
	count === 1 ? m.mail_rule_mails_one() : m.mail_rule_mails({ count });

/** A stored rule as the dry run takes it, in place of itself (`rule_id`). */
export function dryRunBody(rule: MailRule): MailRuleDryRun {
	return {
		mailbox_id: rule.mailbox_id,
		name: rule.name,
		priority: rule.priority,
		conditions: rule.conditions,
		parts: rule.parts,
		user_id: rule.user_id,
		space_id: rule.space_id,
		text_type_id: rule.text_type_id,
		after: rule.after,
		rule_id: rule.id
	};
}

export function createBody(form: MailRuleForm): MailRuleCreate {
	return { mailbox_id: form.mailboxId, ...body(form) };
}

export function patchBody(form: MailRuleForm): MailRulePatch {
	return body(form);
}

export interface Names {
	user: (id: string | null | undefined) => string;
	space: (id: string | null | undefined) => string;
	type: (id: string | null | undefined) => string;
}

/** A condition in words ("Absender endet auf @stadtwerke.example"). */
export function conditionText(item: Pick<MailConditionNode, 'field' | 'op' | 'value'>): string {
	return [
		FIELD_LABELS[item.field](),
		operatorText(item.field, item.op),
		item.value ? valueText(item.field, item.value) : ''
	]
		.filter(Boolean)
		.join(' ');
}

function valueText(field: MailField, value: string): string {
	switch (field) {
		case 'folder':
			return quoted(folderLabel(value));
		case 'importance':
			return importanceLabel(value);
		case 'flag':
			return flagLabel(value);
		default:
			return value;
	}
}

/** A step on the mail in words ("Schlagwort „Lekto“ hinzufügen"). */
export function stepText(step: { action: MailAction; value?: string | null }): string {
	const value = step.value ?? '';
	switch (step.action) {
		case 'read':
			return m.mail_rule_after_read();
		case 'unread':
			return m.mail_rule_after_unread();
		case 'flag':
			return m.mail_rule_after_flag({ color: flagLabel(value) });
		case 'unflag':
			return m.mail_rule_after_unflag();
		case 'add_keyword':
			return m.mail_rule_after_add_keyword({ keyword: value });
		case 'remove_keyword':
			return m.mail_rule_after_remove_keyword({ keyword: value });
		case 'move':
			return m.mail_rule_summary_move({ folder: folderLabel(value) });
		case 'trash':
			return m.mail_rule_after_trash();
	}
}

/** What the rule does, one part each: what it takes, for whom, where, the type of the text,
 * the mail afterwards. */
export function actionTexts(rule: MailRule, names: Names): string[] {
	const does: string[] = [PARTS_LABELS[rule.parts]()];
	if (rule.user_id) does.push(m.mail_rule_summary_for({ name: names.user(rule.user_id) }));
	if (rule.space_id) does.push(m.mail_rule_summary_space({ name: names.space(rule.space_id) }));
	if (rule.text_type_id)
		does.push(m.mail_rule_summary_type({ name: names.type(rule.text_type_id) }));
	for (const step of rule.after) does.push(stepText(step));
	return does;
}

/** A rule in one line: its priority, its conditions, then what it does. */
export function summaryOf(rule: MailRule, names: Names): string {
	const tree = treeOf(rule);
	const when = tree.items.length ? treeText(tree, conditionText) : m.mail_rule_every();
	return `${m.rule_priority_short({ priority: rule.priority })} · ${when} → ${actionTexts(rule, names).join(', ')}`;
}
