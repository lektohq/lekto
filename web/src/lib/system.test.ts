import { describe, expect, it } from 'vitest';
import { monthLabel, systemTab, systemTabs } from './system.ts';

describe('the tab of the page "System"', () => {
	it('is the one the URL names, else the first', () => {
		expect(systemTab(new URLSearchParams('tab=jobs'), true)).toBe('jobs');
		expect(systemTab(new URLSearchParams('tab=search'), true)).toBe('search');
		expect(systemTab(new URLSearchParams(''), true)).toBe('jobs');
		expect(systemTab(new URLSearchParams('tab=classifier'), true)).toBe('classifier');
		expect(systemTab(new URLSearchParams('tab=nonsense'), true)).toBe('jobs');
		expect(systemTab(new URLSearchParams('tab=maintenance'), true)).toBe('jobs');
		expect(systemTab(new URLSearchParams('tab=intake'), true)).toBe('intake');
		expect(systemTab(new URLSearchParams('tab=intake'), false)).toBe('jobs');
	});

	it('keeps the intake channels to admins', () => {
		expect(systemTabs(true)).toContain('intake');
		expect(systemTabs(false)).not.toContain('intake');
	});
});

describe('the label of a month on the history', () => {
	it('names the month, with the year across years', () => {
		expect(monthLabel('2026-10-01', false)).toMatch(/^(Oct|Okt)/);
		expect(monthLabel('2026-10-01', false)).not.toMatch(/26/);
		expect(monthLabel('2025-10-01', true)).toMatch(/^(Oct|Okt)\.? ?25$/);
	});
});
