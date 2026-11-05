/**
 * What a mail is marked with (Tobi, 05.11.2026; `lekto.core.domain.mail_traits`): its
 * importance, its keywords on the server and its flag in Apple Mail's colours. Mail rules,
 * document rules and a document's origin say them in the same words.
 */
import type { components } from '#lib/api/schema.ts';
import { m } from '#lib/paraglide/messages.js';

export type Importance = components['schemas']['Importance'];
export type FlagColor = components['schemas']['FlagColor'];

export const IMPORTANCES: readonly Importance[] = ['high', 'normal', 'low'];
export const FLAG_COLORS: readonly FlagColor[] = [
	'red',
	'orange',
	'yellow',
	'green',
	'blue',
	'purple',
	'gray'
];

const IMPORTANCE_LABELS: Record<Importance, () => string> = {
	high: m.mail_importance_high,
	normal: m.mail_importance_normal,
	low: m.mail_importance_low
};

const FLAG_LABELS: Record<FlagColor, () => string> = {
	red: m.mail_flag_red,
	orange: m.mail_flag_orange,
	yellow: m.mail_flag_yellow,
	green: m.mail_flag_green,
	blue: m.mail_flag_blue,
	purple: m.mail_flag_purple,
	gray: m.mail_flag_gray
};

export const importanceLabel = (value: string): string =>
	IMPORTANCE_LABELS[value as Importance]?.() ?? value;
export const flagLabel = (value: string): string => FLAG_LABELS[value as FlagColor]?.() ?? value;

export const importanceOptions = () =>
	IMPORTANCES.map((value) => ({ value, label: IMPORTANCE_LABELS[value]() }));
export const flagOptions = () =>
	FLAG_COLORS.map((value) => ({ value, label: FLAG_LABELS[value]() }));

/** A keyword IMAP can carry: 1 to 100 printable ASCII characters, none of `(){ %*"\]`. */
export function isKeyword(value: string): boolean {
	return /^[\x21-\x7e]{1,100}$/.test(value) && !/[(){%*"\\\]]/.test(value);
}

/** The keywords to choose from, with `value` kept when it is none of them. */
export function keywordOptions(keywords: readonly string[], value = '') {
	const all = value && !keywords.includes(value) ? [...keywords, value] : [...keywords];
	return all.map((name) => ({ value: name, label: name }));
}
