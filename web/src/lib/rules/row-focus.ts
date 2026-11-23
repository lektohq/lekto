/**
 * Where the focus goes when a row of a rule's conditions or actions moves or is removed with
 * the keyboard: it stays with the row, never on the page. A row's frame carries
 * `data-rule-row`, its buttons `data-row` ("up", "down", "remove"), and what adds a row to its
 * list `data-row="add"`.
 */
import { tick } from 'svelte';

const frame = (element: Element | null) => element?.closest<HTMLElement>('[data-rule-row]') ?? null;
const button = (row: Element | null, name: string) =>
	row?.querySelector<HTMLButtonElement>(`[data-row="${name}"]`) ?? null;

/** Move the row of `from` (its "up" or "down") and keep the focus on that button at the row's
 * new place, or on the other one where this way ends there (the first or the last place). */
export async function moveKeepingFocus(from: HTMLElement, act: () => void): Promise<void> {
	const row = frame(from);
	const way = from.dataset.row === 'up' ? 'up' : 'down';
	act();
	await tick();
	const same = button(row, way);
	const other = button(row, way === 'up' ? 'down' : 'up');
	(same && !same.disabled ? same : other && !other.disabled ? other : same)?.focus();
}

/** Remove the row of `from` and put the focus where it was: on the row that follows, else the
 * one before, else on what adds a row to the list. */
export async function removeKeepingFocus(from: HTMLElement, act: () => void): Promise<void> {
	const row = frame(from);
	const list = row?.parentElement ?? null;
	const isRow = (element: Element | null | undefined): element is HTMLElement =>
		element instanceof HTMLElement && element.hasAttribute('data-rule-row');
	const beside = isRow(row?.nextElementSibling)
		? row.nextElementSibling
		: isRow(row?.previousElementSibling)
			? row.previousElementSibling
			: null;
	act();
	await tick();
	const next = beside?.isConnected ? button(beside, 'remove') : null;
	// The list's own way to add a row: not one of a group inside it.
	const add = [...(list?.querySelectorAll<HTMLElement>('[data-row="add"]') ?? [])].findLast(
		(candidate) =>
			!candidate.hasAttribute('disabled') &&
			(candidate.closest('[data-rule-row]') ?? null) === (list?.closest('[data-rule-row]') ?? null)
	);
	(next ?? add ?? null)?.focus();
}
