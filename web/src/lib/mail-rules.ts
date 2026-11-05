/**
 * Mail rules (Regeln › Mails; Tobi, 04.11.2026, mock E): what a mailbox's mails bring in. The
 * form of the editor as the API takes it, and a rule in one line for the list.
 */
import type { components } from '#lib/api/schema.ts';
import { flagLabel, importanceLabel, isKeyword } from '#lib/mail-traits.ts';
import { folderLabel } from '#lib/mailboxes.ts';
import { m } from '#lib/paraglide/messages.js';
import { operatorLabel } from '#lib/rules/describe.ts';
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
export type MailField = components['schemas']['MailField'];
export type MailOperator = components['schemas']['MailOperator'];
export type MailParts = components['schemas']['MailParts'];
export type MailAction = components['schemas']['MailAction'];
export type DryRunMail = components['schemas']['DryRunMailOut'];
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

export const OPERATORS: Record<MailField, readonly MailOperator[]> = {
	sender: ['ends_with', 'contains', 'is', 'starts_with'],
	recipient: ['ends_with', 'contains', 'is', 'starts_with'],
	to: ['ends_with', 'contains', 'is', 'starts_with'],
	cc: ['ends_with', 'contains', 'is', 'starts_with'],
	subject: ['contains', 'is', 'starts_with', 'ends_with'],
	folder: ['is'],
	attachments: ['present', 'missing'],
	importance: ['is'],
	keyword: ['contains', 'present', 'missing'],
	flag: ['present', 'missing', 'is']
};

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

export const FIELD_LABELS: Record<MailField, () => string> = {
	sender: m.mail_rule_field_sender,
	recipient: m.mail_rule_field_recipient,
	to: m.mail_rule_field_to,
	cc: m.mail_rule_field_cc,
	subject: m.mail_rule_field_subject,
	folder: m.mail_rule_field_folder,
	attachments: m.mail_rule_field_attachments,
	importance: m.mail_rule_field_importance,
	keyword: m.mail_rule_field_keyword,
	flag: m.mail_rule_field_flag
};

/** A comparison in the words of the document rules' mail fields ("ist", "endet auf",
 * "Schlagwörter enthalten"); attachments are there or not. */
export function operatorText(field: MailField, op: MailOperator): string {
	if (field === 'attachments') {
		return op === 'present' ? m.mail_rule_attachments_present() : m.mail_rule_attachments_missing();
	}
	return operatorLabel(field === 'keyword' ? 'mail_keyword' : 'mail_sender', op);
}

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

function stepValid(step: StepForm): boolean {
	const value = step.value.trim();
	switch (step.action) {
		case 'add_keyword':
		case 'remove_keyword':
			return isKeyword(value);
		case 'move':
			return value !== '';
		case 'flag':
			return value !== '';
		default:
			return true;
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
			priority: '100',
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

/** Whether the form can be saved. */
export function complete(form: MailRuleForm): boolean {
	const priority = Number(form.priority);
	const takes = form.parts !== 'nothing';
	return (
		form.mailboxId !== '' &&
		form.name.trim() !== '' &&
		Number.isInteger(priority) &&
		priority >= 0 &&
		priority <= 1000 &&
		(!takes || form.userId !== '') &&
		form.steps.every(stepValid) &&
		emptyGroups(form.conditions, false).length === 0 &&
		conditionsOf(form.conditions).every(
			(item) =>
				!hasValue(item.op) ||
				(item.field === 'keyword' ? isKeyword(item.value.trim()) : item.value.trim() !== '')
		)
	);
}

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
			return `„${folderLabel(value)}“`;
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
