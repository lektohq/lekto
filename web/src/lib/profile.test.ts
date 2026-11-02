import { describe, expect, it } from 'vitest';
import { settingsTab } from './profile.ts';

describe('settingsTab', () => {
	it('takes the tab from the address, else the first', () => {
		expect(settingsTab(new URLSearchParams('tab=identifiers'))).toBe('identifiers');
		expect(settingsTab(new URLSearchParams(''))).toBe('profile');
		expect(settingsTab(new URLSearchParams('tab=nonsense'))).toBe('profile');
	});

	it('shows the sign-in where linking an account came back with an error', () => {
		expect(settingsTab(new URLSearchParams('error=denied'))).toBe('sign-in');
		expect(settingsTab(new URLSearchParams('tab=tokens&error=denied'))).toBe('tokens');
	});
});
