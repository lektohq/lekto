/**
 * Mail rules (Regeln › Mails; Tobi, 04.11.2026, mock E): what a mailbox's mails bring in. The
 * form of the editor as the API takes it, and a rule in one line for the list.
 */
import type { components } from '#lib/api/schema.ts';
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
	'subject',
	'folder',
	'attachments'
];

export const OPERATORS: Record<MailField, readonly MailOperator[]> = {
	sender: ['ends_with', 'contains', 'is', 'starts_with'],
	recipient: ['ends_with', 'contains', 'is', 'starts_with'],
	subject: ['contains', 'is', 'starts_with', 'ends_with'],
	folder: ['is'],
	attachments: ['present', 'missing']
};

export const PARTS: readonly MailParts[] = ['all', 'attachments', 'text', 'nothing'];
export const AFTER: readonly MailAction[] = ['nothing', 'read', 'move', 'trash'];

export const FIELD_LABELS: Record<MailField, () => string> = {
	sender: m.mail_rule_field_sender,
	recipient: m.mail_rule_field_recipient,
	subject: m.mail_rule_field_subject,
	folder: m.mail_rule_field_folder,
	attachments: m.mail_rule_field_attachments
};

/** A comparison in the words of the document rules' ("ist", "endet auf"); attachments are
 * there or not. */
export function operatorText(field: MailField, op: MailOperator): string {
	if (field === 'attachments') {
		return op === 'present' ? m.mail_rule_attachments_present() : m.mail_rule_attachments_missing();
	}
	return operatorLabel('mail_sender', op);
}

export const PARTS_LABELS: Record<MailParts, () => string> = {
	all: m.mail_rule_parts_all,
	attachments: m.mail_rule_parts_attachments,
	text: m.mail_rule_parts_text,
	nothing: m.mail_rule_parts_nothing
};

export const AFTER_LABELS: Record<MailAction, () => string> = {
	nothing: m.mail_rule_after_nothing,
	read: m.mail_rule_after_read,
	move: m.mail_rule_after_move,
	trash: m.mail_rule_after_trash
};

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
export type Optional = 'space' | 'type' | 'after';
export const OPTIONALS: readonly Optional[] = ['space', 'type', 'after'];

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
	after: MailAction;
	moveTo: string;
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
			after: 'nothing',
			moveTo: '',
			shown: typeId ? ['type'] : []
		};
	}
	const shown: Optional[] = [];
	if (rule.space_id) shown.push('space');
	if (rule.text_type_id) shown.push('type');
	if (rule.after !== 'nothing') shown.push('after');
	return {
		mailboxId: rule.mailbox_id,
		name: rule.name,
		priority: String(rule.priority),
		conditions: treeOf(rule),
		parts: rule.parts,
		userId: rule.user_id ?? '',
		spaceId: rule.space_id ?? '',
		typeId: rule.text_type_id ?? '',
		after: rule.after,
		moveTo: rule.move_to ?? '',
		shown
	};
}

/** Whether the form can be saved. */
export function complete(form: MailRuleForm): boolean {
	const priority = Number(form.priority);
	const takes = form.parts !== 'nothing';
	const after = form.shown.includes('after') ? form.after : 'nothing';
	return (
		form.mailboxId !== '' &&
		form.name.trim() !== '' &&
		Number.isInteger(priority) &&
		priority >= 0 &&
		priority <= 1000 &&
		(!takes || form.userId !== '') &&
		(after !== 'move' || form.moveTo.trim() !== '') &&
		emptyGroups(form.conditions, false).length === 0 &&
		conditionsOf(form.conditions).every((item) => !hasValue(item.op) || item.value.trim() !== '')
	);
}

function body(form: MailRuleForm) {
	const takes = form.parts !== 'nothing';
	const after = form.shown.includes('after') ? form.after : 'nothing';
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
		after,
		move_to: after === 'move' ? form.moveTo.trim() : null
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
		item.value ? (item.field === 'folder' ? `„${folderLabel(item.value)}“` : item.value) : ''
	]
		.filter(Boolean)
		.join(' ');
}

/** What the rule does, one part each: what it takes, for whom, where, the type of the text,
 * the mail afterwards. */
export function actionTexts(rule: MailRule, names: Names): string[] {
	const does: string[] = [PARTS_LABELS[rule.parts]()];
	if (rule.user_id) does.push(m.mail_rule_summary_for({ name: names.user(rule.user_id) }));
	if (rule.space_id) does.push(m.mail_rule_summary_space({ name: names.space(rule.space_id) }));
	if (rule.text_type_id)
		does.push(m.mail_rule_summary_type({ name: names.type(rule.text_type_id) }));
	if (rule.after === 'move' && rule.move_to) {
		does.push(m.mail_rule_summary_move({ folder: folderLabel(rule.move_to) }));
	} else if (rule.after !== 'nothing') {
		does.push(AFTER_LABELS[rule.after]());
	}
	return does;
}

/** A rule in one line: its priority, its conditions, then what it does. */
export function summaryOf(rule: MailRule, names: Names): string {
	const tree = treeOf(rule);
	const when = tree.items.length ? treeText(tree, conditionText) : m.mail_rule_every();
	return `${m.rule_priority_short({ priority: rule.priority })} · ${when} → ${actionTexts(rule, names).join(', ')}`;
}
