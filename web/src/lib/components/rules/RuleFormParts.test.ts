// The parts the editors of a document rule and of a mail rule share (web/DESIGN.md, "Mail
// rules": one set of parts for every rule).
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import mailRuleForm from './MailRuleForm.svelte?raw';
import ruleBuilder from './RuleBuilder.svelte?raw';
import RuleFormFoot from './RuleFormFoot.svelte';
import RuleFormHead from './RuleFormHead.svelte';

describe('the parts of the editor of a rule (WD-05)', () => {
	it('names the rule and its priority, each with its problem', () => {
		render(RuleFormHead, {
			name: 'Rechnungen',
			priority: 100,
			errors: { name: 'no name', priority: 'not a number' },
			prefix: 'rule'
		});
		const name = screen.getByLabelText(m.field_name()) as HTMLInputElement;
		const priority = screen.getByLabelText(m.rule_priority()) as HTMLInputElement;
		expect([name.id, name.value, name.getAttribute('aria-invalid')]).toEqual([
			'rule-name',
			'Rechnungen',
			'true'
		]);
		expect([priority.id, priority.value]).toEqual(['rule-priority', '100']);
		// The hint stays where it is, the problem comes below it: the same in both editors.
		const field = priority.closest('[data-slot="field"]')!;
		expect(field.textContent).toMatch(
			new RegExp(`${m.rule_priority_hint().slice(0, 20)}[\\s\\S]*not a number`)
		);
		expect(
			screen.queryByRole('button', { name: m.hint_about({ name: m.rule_priority() }) })
		).toBeNull();
	});

	it('has more to say about the priority where the kind of rule does', () => {
		render(RuleFormHead, {
			name: '',
			priority: '100',
			errors: {},
			prefix: 'mail-rule',
			priorityInfo: m.mail_rule_priority_info()
		});
		expect(
			screen.getByRole('button', { name: m.hint_about({ name: m.rule_priority() }) })
		).toBeTruthy();
		expect(screen.getByLabelText(m.rule_priority()).id).toBe('mail-rule-priority');
	});

	it('ends with the problem, the way back and "Speichern und Probelauf", held while it saves', () => {
		render(RuleFormFoot, { error: 'changed meanwhile', held: true, cancelHref: '/ui/rules' });
		expect(screen.getByRole('alert').textContent).toContain('changed meanwhile');
		expect(screen.getByRole('link', { name: m.cancel() }).getAttribute('href')).toBe('/ui/rules');
		expect(
			(screen.getByRole('button', { name: m.rule_save() }) as HTMLButtonElement).disabled
		).toBe(true);
	});

	it.each([
		['RuleBuilder', ruleBuilder],
		['MailRuleForm', mailRuleForm]
	])('%s builds none of them by hand', (_name, source) => {
		for (const part of ['<RuleFormHead', '<RuleFormFoot', '<AddActionMenu']) {
			expect(source).toContain(part);
		}
		// Each stands in its part alone.
		for (const own of [
			'm.rule_save()',
			'm.rule_save_hint()',
			'm.rule_add_action()',
			'm.rule_priority()'
		]) {
			expect(source).not.toContain(own);
		}
	});
});
