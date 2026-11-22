import { render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import { session } from '#lib/session.svelte.ts';
import { signIn } from '#lib/testing/session.ts';
import TitlePatternBadge from './TitlePatternBadge.svelte';

const props = { documentTypeId: 't1', name: 'Rechnung', ruleId: 'r1' };
const words = m.rule_title_pattern_of({ type: 'Rechnung' });

afterEach(() => session.clear());

describe('the badge of a title pattern (WD-10)', () => {
	it('opens the type for an admin, with a hit area a finger tall on a phone', () => {
		signIn('admin');
		render(TitlePatternBadge, props);
		// 16 px of text: 12 px above and below with a mouse, 14 px on a phone.
		expect(screen.getByRole('button', { name: words }).className.split(' ')).toEqual(
			expect.arrayContaining(['after:absolute', 'after:-inset-y-3', 'max-sm:after:-inset-y-3.5'])
		);
	});

	it('is words alone for everyone else', () => {
		signIn('user');
		render(TitlePatternBadge, props);
		expect(screen.queryByRole('button')).toBeNull();
		expect(screen.getByText(words)).toBeTruthy();
	});
});
