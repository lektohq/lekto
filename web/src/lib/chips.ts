/**
 * Values written as chips (a contact's other spellings): what typing or pasting adds.
 */

/** What a chip field takes, as the API does: the length of one value, the number of values. */
export interface ChipLimits {
	maxlength: number;
	max: number;
}

/** `values` with the lines of `text` after them: trimmed, empty lines and values there already
 * (regardless of case) left out. A line longer than `maxlength`, or beyond `max` values, is not
 * added but comes back in `left` (joined by spaces), so nothing pasted is lost unseen. */
export function addChips(
	values: readonly string[],
	text: string,
	{ maxlength, max }: ChipLimits
): { values: string[]; left: string } {
	const next = [...values];
	const left: string[] = [];
	for (const line of text.split('\n')) {
		const value = line.trim();
		const known = next.some((other) => other.toLocaleLowerCase() === value.toLocaleLowerCase());
		if (value === '' || known) continue;
		if (value.length > maxlength || next.length >= max) left.push(value);
		else next.push(value);
	}
	return { values: next, left: left.join(' ') };
}
