/**
 * What the pickers share: a choice of several values turned on or off, and a typed query held
 * against the labels of the options. One rule for every search in this browser, the pickers,
 * the tags and the master data lists alike: every word of the query stands somewhere in what
 * an option is about, regardless of case and of the order of the words ("Bäckerei Muster"
 * finds "Muster Bäckerei").
 */

/** `selected` with `value` in it (`on`) or without it. */
export function toggled(selected: readonly string[], value: string, on: boolean): string[] {
	return on ? [...selected, value] : selected.filter((entry) => entry !== value);
}

/** `selected` with `value` taken out if it is in it, else added: a chip tapped. */
export function flipped(selected: readonly string[], value: string): string[] {
	return toggled(selected, value, !selected.includes(value));
}

/** A query as it is held against the options: trimmed, regardless of case. */
export function searchWords(query: string): string {
	return query.trim().toLocaleLowerCase();
}

/** Whether `text` holds every word of `words` (from `searchWords`); no words match everything. */
export function matchesWords(text: string, words: string): boolean {
	const held = text.toLocaleLowerCase();
	return words.split(/\s+/).every((word) => held.includes(word));
}

/** Whether every word of `query` stands in one of `texts`, regardless of case. */
export function matchesAllWords(
	query: string,
	texts: readonly (string | null | undefined)[]
): boolean {
	return matchesWords(
		texts.filter((text): text is string => !!text).join('\n'),
		searchWords(query)
	);
}

/**
 * `items` by name under their first letter, as `locale` sorts them. Letters the language files
 * as one (A, a and Ä in German; not Ä in Swedish, which comes after Z) share a group under the
 * plain one, so that no letter comes twice: sorting and grouping follow the same rule.
 */
export function byLetter<T extends { label: string }>(
	items: readonly T[],
	locale: string
): { letter: string; items: T[] }[] {
	const collator = new Intl.Collator(locale, { sensitivity: 'base' });
	// Space around a name counts for neither, or the two would disagree.
	const name = (item: T) => item.label.trim();
	const first = (item: T) => (Array.from(name(item))[0] ?? '').toLocaleUpperCase(locale);
	const groups: { letter: string; items: T[] }[] = [];
	for (const item of items.toSorted((a, b) => collator.compare(name(a), name(b)))) {
		const letter = first(item);
		const last = groups.at(-1);
		if (last && collator.compare(last.letter, letter) === 0) {
			last.items.push(item);
			// "A" before "Ä": the group is named by the plain letter.
			if (letter < last.letter) last.letter = letter;
		} else {
			groups.push({ letter, items: [item] });
		}
	}
	return groups;
}
