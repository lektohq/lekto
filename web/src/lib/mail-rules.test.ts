import { describe, expect, it } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import {
	addableSteps,
	complete,
	conditionText,
	createBody,
	dryRunBody,
	formOf,
	mailsCount,
	newCondition,
	patchBody,
	stepText,
	summaryOf,
	validate,
	withStep,
	type MailConditionNode,
	type MailRule
} from './mail-rules.ts';
import { CONDITION_FIELD_OPERATORS } from '#lib/rules/model.ts';
import { newGroup } from '#lib/rules/tree.ts';
import { OPERATORS } from './mail-rules.ts';

const RULE: MailRule = {
	id: 'r1',
	mailbox_id: 'm1',
	name: 'Strom',
	priority: 1,
	conditions: {
		any: [
			{ field: 'sender', op: 'ends_with', value: '@stadtwerke.example' },
			{ field: 'attachments', op: 'present', value: null }
		],
		not: false
	},
	parts: 'all',
	user_id: 'u1',
	space_id: 's1',
	text_type_id: null,
	after: [
		{ action: 'add_keyword', value: 'Lekto' },
		{ action: 'move', value: 'Lekto/Erledigt' }
	],
	enabled: true,
	disabled_reason: null,
	created_at: '2026-11-04T10:00:00Z',
	updated_at: '2026-11-04T10:00:00Z'
};

const names = { user: () => 'Max', space: () => 'Haushalt', type: () => 'E-Mail' };

describe('the form of a mail rule', () => {
	it('starts for a mailbox with its type of the mail text', () => {
		const form = formOf(null, 'm1', 't1');
		expect([form.mailboxId, form.typeId, form.shown, form.parts]).toEqual([
			'm1',
			't1',
			['type'],
			'all'
		]);
		expect(complete(form)).toBe(false); // no name, no person, an empty condition
		form.name = 'Strom';
		form.userId = 'u1';
		(form.conditions.items[0] as MailConditionNode).value = '@stadtwerke.example';
		expect(complete(form)).toBe(true);
		expect(createBody(form)).toMatchObject({
			mailbox_id: 'm1',
			name: 'Strom',
			user_id: 'u1',
			text_type_id: 't1',
			space_id: null,
			after: [],
			conditions: {
				all: [{ field: 'sender', op: 'ends_with', value: '@stadtwerke.example' }],
				not: false
			}
		});
		form.conditions.items = [];
		expect(createBody(form).conditions).toBeNull(); // no conditions: every mail
	});

	it('keeps what a stored rule has, and drops what is taken away', () => {
		const form = formOf(RULE);
		expect(form.shown).toEqual(['space']);
		expect(patchBody(form)).toMatchObject({ space_id: 's1', after: RULE.after });
		form.shown = [];
		form.steps = [];
		expect(patchBody(form)).toMatchObject({ space_id: null, after: [] });
		form.parts = 'nothing';
		expect(patchBody(form)).toMatchObject({ user_id: null, parts: 'nothing' });
		form.conditions.items.push(newCondition('attachments'));
		expect(complete(form)).toBe(true); // "present" takes no value
		form.conditions.items.push(newGroup<MailConditionNode>('all', []));
		expect(complete(form)).toBe(false); // an empty subgroup
	});

	it('says the marks and importance of a mail, and takes only a keyword IMAP can carry', () => {
		expect(conditionText({ field: 'importance', op: 'is', value: 'high' })).toBe(
			`${m.mail_rule_field_importance()} ${m.rule_op_is()} ${m.mail_importance_high()}`
		);
		expect(conditionText({ field: 'flag', op: 'is', value: 'green' })).toBe(
			`${m.mail_rule_field_flag()} ${m.rule_op_is()} ${m.mail_flag_green()}`
		);
		expect(conditionText({ field: 'keyword', op: 'contains', value: 'Lekto' })).toBe(
			`${m.mail_rule_field_keyword()} ${m.rule_op_tags_contains()} Lekto`
		);
		expect(conditionText({ field: 'cc', op: 'is', value: 'ben@example.test' })).toBe(
			`${m.mail_rule_field_cc()} ${m.rule_op_is()} ben@example.test`
		);
		const form = formOf(RULE);
		const keyword = newCondition('keyword');
		form.conditions.items.push(keyword);
		keyword.value = 'zwei Wörter';
		expect(complete(form)).toBe(false);
		keyword.value = '$label1';
		expect(complete(form)).toBe(true);
	});

	it('keeps a move or the trash last, once, and steps without a value once', () => {
		let steps = withStep([], 'move');
		steps = withStep(steps, 'read');
		steps = withStep(steps, 'flag');
		expect(steps.map((step) => step.action)).toEqual(['read', 'flag', 'move']);
		expect(addableSteps(steps)).toEqual([
			'unread',
			'flag',
			'unflag',
			'add_keyword',
			'remove_keyword'
		]);
		const form = formOf(RULE);
		form.steps = steps;
		expect(complete(form)).toBe(false); // the move names no folder
		steps[2].value = 'Erledigt';
		expect(complete(form)).toBe(true);
		expect(createBody(form).after).toEqual([
			{ action: 'read', value: null },
			{ action: 'flag', value: 'red' },
			{ action: 'move', value: 'Erledigt' }
		]);
		expect(stepText({ action: 'flag', value: 'blue' })).toBe(
			m.mail_rule_after_flag({ color: m.mail_flag_blue() })
		);
	});

	it('keeps groups and their "not" as the tree of every rule', () => {
		const nested: MailRule = {
			...RULE,
			conditions: {
				all: [
					{ field: 'sender', op: 'ends_with', value: '@stadtwerke.example' },
					{ any: [{ field: 'subject', op: 'contains', value: 'Mahnung' }], not: true }
				],
				not: false
			}
		};
		expect(patchBody(formOf(nested)).conditions).toEqual(nested.conditions);
		expect(summaryOf(nested, names)).toContain(
			`${m.rule_and()}${m.rule_not_text({ text: `${m.mail_rule_field_subject()} ${m.rule_op_contains()} Mahnung` })}`
		);
	});

	it('names what is wrong, by the key of its block', () => {
		const form = formOf(null, '', '');
		form.priority = '1001';
		const condition = form.conditions.items[0] as MailConditionNode;
		const keyword = newCondition('keyword');
		keyword.value = 'zwei Wörter';
		form.conditions.items.push(keyword, newGroup<MailConditionNode>('any', []));
		form.steps = withStep([], 'move');
		const problems = validate(form);
		expect(problems).toEqual({
			name: m.rule_error_name(),
			priority: m.rule_error_priority(),
			mailbox: m.rule_error_choose(),
			user: m.rule_error_choose(),
			[condition.key]: m.rule_error_value(),
			[keyword.key]: m.mail_rule_error_keyword(),
			[form.conditions.items[2].key]: m.rule_error_group_empty(),
			[form.steps[0].key]: m.rule_error_value()
		});
		form.parts = 'nothing';
		expect(validate(form).user).toBeUndefined(); // takes nothing: no person needed
	});

	it('offers each field the comparisons the document rules offer for the mail', () => {
		expect(OPERATORS.subject).toEqual(CONDITION_FIELD_OPERATORS.mail_subject);
		expect(OPERATORS.sender).toEqual(CONDITION_FIELD_OPERATORS.mail_sender);
		expect(OPERATORS.keyword).toEqual(CONDITION_FIELD_OPERATORS.mail_keyword);
		expect(OPERATORS.flag).toEqual(CONDITION_FIELD_OPERATORS.mail_flag);
		expect(newCondition('subject').op).toBe(CONDITION_FIELD_OPERATORS.mail_subject[0]);
	});

	it('counts mails and sends a stored rule to its dry run as it is', () => {
		expect(mailsCount(1)).toBe(m.mail_rule_mails_one());
		expect(mailsCount(12)).toBe(m.mail_rule_mails({ count: 12 }));
		expect(dryRunBody(RULE)).toEqual({
			mailbox_id: 'm1',
			name: 'Strom',
			priority: 1,
			conditions: RULE.conditions,
			parts: 'all',
			user_id: 'u1',
			space_id: 's1',
			text_type_id: null,
			after: RULE.after,
			rule_id: 'r1'
		});
	});

	it('wants a space the person edits', () => {
		const form = formOf(RULE);
		const spaces = [
			{ id: 's1', name: 'Haushalt', personal_of: null, members: [{ user_id: 'u1', role: 'edit' }] }
		] as unknown as Parameters<typeof validate>[1];
		expect(validate(form, spaces).space).toBeUndefined();
		form.spaceId = 'gone';
		expect(validate(form, spaces).space).toBe(m.rule_error_choose());
	});

	it('says a rule in one line', () => {
		expect(summaryOf(RULE, names)).toBe(
			`${m.rule_priority_short({ priority: 1 })} · ${m.mail_rule_field_sender()} ${m.rule_op_ends_with()} @stadtwerke.example${m.rule_or()}${m.mail_rule_field_attachments()} ${m.mail_rule_attachments_present()} → ${m.mail_rule_parts_all()}, ${m.mail_rule_summary_for({ name: 'Max' })}, ${m.mail_rule_summary_space({ name: 'Haushalt' })}, ${m.mail_rule_after_add_keyword({ keyword: 'Lekto' })}, ${m.mail_rule_summary_move({ folder: 'Lekto/Erledigt' })}`
		);
		expect(
			summaryOf(
				{
					...RULE,
					conditions: null,
					parts: 'nothing',
					user_id: null,
					space_id: null,
					after: [{ action: 'trash' }]
				},
				names
			)
		).toContain(m.mail_rule_every());
	});
});
