// The value of what a mail was marked with, one input for every rule (web/DESIGN.md, "Mail
// rules").
import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import { phone } from '#lib/phone.svelte.ts';
import { choose, optionsOf, selectedValue } from '#lib/testing/select.ts';
import conditionRow from './ConditionRow.svelte?raw';
import mailRuleForm from './MailRuleForm.svelte?raw';
import MailValueInput from './MailValueInput.svelte';

afterEach(() => phone.override(null));

describe('the value of a mark of a mail (WD-05)', () => {
	it('is a choice for importance and flag: "Bitte wählen …" first, in every editor', async () => {
		// The two editors each drew it: the importance once with and once without it.
		phone.override(true);
		for (const trait of ['importance', 'flag'] as const) {
			const onchange = vi.fn();
			const { unmount } = render(MailValueInput, { trait, value: '', label: 'Value', onchange });
			const field = screen.getByRole('combobox', { name: 'Value' });
			const options = await optionsOf(field);
			expect(options[0]).toEqual({ value: '', label: m.rule_choose() });
			expect(options.length).toBeGreaterThan(2);
			await choose(userEvent.setup(), field, options[1].value);
			expect(onchange).toHaveBeenLastCalledWith(options[1].value);
			unmount();
		}
	});

	it('keeps a value it no longer knows, and names it so', async () => {
		phone.override(true);
		render(MailValueInput, { trait: 'flag', value: 'pink', label: 'Value', onchange: vi.fn() });
		const field = screen.getByRole('combobox', { name: 'Value' });
		expect(selectedValue(field)).toBe('pink');
		expect((await optionsOf(field)).at(-1)).toEqual({ value: 'pink', label: m.rule_unknown() });
	});

	it('searches a keyword among those given, the one set among them', () => {
		render(MailValueInput, {
			trait: 'keyword',
			value: 'Lekto',
			keywords: ['Rechnung'],
			label: 'Value',
			invalid: true,
			onchange: vi.fn()
		});
		const field = screen.getByRole('combobox', { name: 'Value' });
		expect(field.textContent).toContain('Lekto');
		expect(field.getAttribute('aria-invalid')).toBe('true');
	});

	it.each([
		['ConditionRow', conditionRow],
		['MailRuleForm', mailRuleForm]
	])('%s draws none of them by itself', (_name, source) => {
		expect(source).toContain('<MailValueInput');
		for (const own of ['importanceOptions', 'flagOptions', 'keywordOptions', 'typedKeyword']) {
			expect(source).not.toContain(own);
		}
	});
});
