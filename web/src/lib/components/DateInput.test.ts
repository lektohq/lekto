import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import { m } from '#lib/paraglide/messages.js';

// The real picker, not the stand-in of the other component tests (`tests/setup.ts`).
vi.unmock('#lib/components/DateInput.svelte');
const { default: DateInput } = await import('./DateInput.svelte');

describe('DateInput', () => {
	it('shows a day in segments of the UI language, with a calendar beside them', () => {
		render(DateInput, { value: '2026-10-26', label: 'Document date' });
		const field = screen.getByRole('group', { name: 'Document date' });
		const parts = [...field.querySelectorAll('[data-segment]')]
			.filter((segment) => segment.getAttribute('data-segment') !== 'literal')
			.map((segment) => segment.textContent?.trim())
			.filter(Boolean);
		expect(parts.sort()).toEqual(['10', '2026', '26']);
		expect(screen.getByRole('button')).toBeTruthy();
	});

	it('adds hour and minute with granularity minute and writes them back', async () => {
		const onchange = vi.fn();
		render(DateInput, {
			value: '2026-10-26T14:30',
			label: 'Came in',
			granularity: 'minute',
			onchange
		});
		const field = screen.getByRole('group', { name: 'Came in' });
		const hour = field.querySelector<HTMLElement>('[data-segment="hour"]');
		expect(hour).toBeTruthy();
		expect(field.querySelector('[data-segment="minute"]')?.textContent?.trim()).toBe('30');
		hour?.focus();
		await fireEvent.keyDown(hour as HTMLElement, { key: 'ArrowUp' });
		expect(onchange).toHaveBeenLastCalledWith('2026-10-26T15:30');
	});

	it('shows the day picked in the calendar after a segment had the focus', async () => {
		const onchange = vi.fn();
		render(DateInput, { value: '2026-10-26', label: 'Document date', onchange });
		const field = screen.getByRole('group', { name: 'Document date' });
		const day = field.querySelector<HTMLElement>('[data-segment="day"]') as HTMLElement;
		day.focus();
		await fireEvent.focusOut(day);
		await fireEvent.click(screen.getByRole('button'));
		const picked = await waitFor(() => {
			const cell = [...document.querySelectorAll<HTMLElement>('[data-bits-day]')].find(
				(cell) => !cell.hasAttribute('data-outside-month') && cell.textContent?.trim() === '20'
			);
			expect(cell).toBeTruthy();
			return cell as HTMLElement;
		});
		await fireEvent.click(picked);
		expect(onchange).toHaveBeenLastCalledWith('2026-10-20');
		await waitFor(() => expect(day.textContent?.trim()).toBe('20'));
	});

	it('names its parts, its calendar and the month buttons in the UI’s words (WY-03)', async () => {
		// The library names them in English whatever the locale ("day, ", "Empty", "Event …",
		// "Previous"), and lays that over a name passed to it.
		render(DateInput, { value: '', label: 'Geburtsdatum' });
		const field = screen.getByRole('group', { name: 'Geburtsdatum' });
		const part = (name: string) => field.querySelector<HTMLElement>(`[data-segment="${name}"]`)!;
		expect(part('day').getAttribute('aria-label')).toBe(m.date_part_day());
		expect(part('month').getAttribute('aria-label')).toBe(m.date_part_month());
		expect(part('year').getAttribute('aria-label')).toBe(m.date_part_year());
		expect(part('day').getAttribute('aria-valuetext')).toBe(m.date_part_empty());
		expect(field.innerHTML).not.toMatch(/"(?:day|month|year), "|Empty/);

		await fireEvent.click(screen.getByRole('button', { name: m.date_pick() }));
		await waitFor(() =>
			expect(screen.getByRole('button', { name: m.date_previous_month() })).toBeTruthy()
		);
		expect(screen.getByRole('button', { name: m.date_next_month() })).toBeTruthy();
		expect(screen.queryByRole('button', { name: 'Previous' })).toBeNull();
		expect(screen.queryByRole('button', { name: 'Next' })).toBeNull();
		// The calendar is named after the field, not "Event".
		const calendar = document.querySelector('[data-calendar-root]');
		expect(calendar?.getAttribute('aria-label') ?? '').not.toMatch(/Event/);
		expect(document.body.innerHTML).not.toMatch(/aria-label="Event\b/);
		expect(document.body.innerHTML).toMatch(/Geburtsdatum,? [^"<]*\d{4}/);
		// The calendar's head is no second banner of the page (WZ-K02).
		expect(screen.queryByRole('banner')).toBeNull();
	});

	it('writes a typed part as its number, not as empty', () => {
		render(DateInput, { value: '2026-10-26', label: 'Geburtsdatum' });
		const day = document.querySelector<HTMLElement>('[data-segment="day"]')!;
		expect(day.getAttribute('aria-valuetext')).toBe('26');
		expect(day.className).not.toContain('text-muted-foreground');
	});

	it('stays empty without a day', () => {
		render(DateInput, { value: '', label: 'Due' });
		const field = screen.getByRole('group', { name: 'Due' });
		expect(field.textContent).not.toMatch(/\d/);
	});
});
