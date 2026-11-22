import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { getLocale, LANGUAGE_NAMES } from '#lib/i18n.ts';
import LanguageMenu from './LanguageMenu.svelte';

describe('the language menu of the sign-in (WB-10)', () => {
	it('is named by what it shows, then by what it is', () => {
		render(LanguageMenu);
		const button = screen.getByRole('button');
		const shown = button.textContent?.trim() ?? '';
		expect(shown).toBe(getLocale().toUpperCase());
		const name = button.getAttribute('aria-label') ?? '';
		expect(name.startsWith(shown)).toBe(true);
		expect(name).toContain(LANGUAGE_NAMES[getLocale()]);
	});
});
