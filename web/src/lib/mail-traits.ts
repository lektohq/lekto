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

export type MailField = components['schemas']['MailField'];
export type MailOperator = components['schemas']['MailOperator'];

/** The comparisons of a mail's fields (DESIGN.md "A mail's fields"), the same in a mail rule
 * and as "Mail: …" in a document rule; a new condition starts with the first. */
/** The fields with a text to compare: an address field, or the subject. */
export const MAIL_TEXT_FIELDS: readonly MailField[] = [
	'sender',
	'recipient',
	'to',
	'cc',
	'subject'
];
const TEXT: readonly MailOperator[] = ['ends_with', 'contains', 'is', 'starts_with'];
export const MAIL_FIELD_OPERATORS: Record<MailField, readonly MailOperator[]> = {
	sender: TEXT,
	recipient: TEXT,
	to: TEXT,
	cc: TEXT,
	subject: TEXT,
	folder: ['is'],
	attachments: ['present', 'missing'],
	importance: ['is'],
	keyword: ['contains', 'present', 'missing'],
	flag: ['present', 'missing', 'is']
};

/** A mail's fields by name ("Absender", "Betreff"): the same words in both kinds of rule. */
export const MAIL_FIELD_LABELS: Record<MailField, () => string> = {
	sender: m.mail_rule_field_sender,
	recipient: m.mail_rule_field_recipient,
	to: m.mail_rule_field_to,
	cc: m.mail_rule_field_cc,
	subject: m.mail_rule_field_subject,
	folder: m.mail_rule_field_folder,
	attachments: m.mail_rule_field_attachments,
	importance: m.mail_rule_field_importance,
	keyword: m.mail_rule_field_keyword,
	flag: m.mail_rule_field_flag
};

/** A keyword typed into a picker as its choice, where IMAP can carry it. */
export async function typedKeyword(name: string): Promise<{ value: string; label: string } | null> {
	const value = name.trim();
	return isKeyword(value) ? { value, label: value } : null;
}
