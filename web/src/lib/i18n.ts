/**
 * Language of the UI and formats of dates and numbers. Paraglide picks the language: the choice
 * stored in this browser, else the browser's language, else English. Texts live in
 * `messages/{de,en}.json`; reasons the API gives with a code are translated (`reasons.ts`),
 * its other texts (problem details) stay as the API sends them.
 */
import { isIsoDay, localDay } from '#lib/dates.ts';
import { m } from '#lib/paraglide/messages.js';
import { getLocale, locales, setLocale, type Locale } from '#lib/paraglide/runtime.js';

export { getLocale, locales, type Locale };

/** Each language in its own words, for the language switch. */
export const LANGUAGE_NAMES: Record<Locale, string> = { de: 'Deutsch', en: 'English' };

const DEFAULT_REGION: Record<Locale, string> = { de: 'de-DE', en: 'en-US' };

/** Switch the language; the page reloads in it and the choice stays in this browser. */
export function changeLanguage(locale: Locale): void {
	if (locale !== getLocale()) setLocale(locale);
}

/**
 * The locale for formats: the browser's own regional variant of the UI language if it has one
 * (`en-GB` for English in Britain), else German as in Germany or English as in the US.
 */
export function regionalLocale(
	locale: Locale,
	preferred: readonly string[] = typeof navigator === 'undefined' ? [] : navigator.languages
): string {
	const own = preferred.find((tag) => tag.toLowerCase().startsWith(`${locale}-`));
	return own ?? DEFAULT_REGION[locale];
}

function formatLocale(): string {
	return regionalLocale(getLocale());
}

/** The locale for lists ("A, B und C"), the same as for dates and numbers. */
export function listLocale(): string {
	return formatLocale();
}

/** A list in the user's language: "A, B und C", or "A, B oder C" for a choice
 * (`disjunction`). The one way to write a list (web/DESIGN.md, "Formats"). */
export function formatList(
	items: readonly string[],
	type: Intl.ListFormatType = 'conjunction'
): string {
	return new Intl.ListFormat(listLocale(), { type }).format(items);
}

/** The browser's time zone (`Europe/Berlin`), which the API needs to count by its days. */
export function browserZone(): string {
	return Intl.DateTimeFormat().resolvedOptions().timeZone;
}

/** A text quoted as the language quotes („…“, “…”). */
export function quoted(text: string): string {
	return m.rule_quoted({ text });
}

/** A moment with its time, the one way to write one (web/DESIGN.md, "Formats"): `medium`
 * "05.11.2026, 14:03" in lines, `short` "05.11.26, 14:03" in the rows of tables. `seconds`
 * only in a log whose entries lie seconds apart (a run's start, the attempts of a delivery):
 * "05.11.2026, 14:03:27". */
export function formatMoment(
	value: Date | string,
	style: 'medium' | 'short' = 'medium',
	seconds = false
): string {
	return formatDate(value, { dateStyle: style, timeStyle: seconds ? 'medium' : 'short' });
}

/**
 * A date (and optionally time) in the user's format. A day (`2026-10-01`) stays that calendar
 * day in every time zone; a moment is shown in the browser's time. Text that is no date comes
 * back as it is.
 */
export function formatDate(
	value: Date | string,
	options: Intl.DateTimeFormatOptions = { dateStyle: 'medium' }
): string {
	const date =
		typeof value !== 'string' ? value : isIsoDay(value) ? localDay(value) : new Date(value);
	if (Number.isNaN(date.getTime())) return typeof value === 'string' ? value : '';
	return new Intl.DateTimeFormat(formatLocale(), options).format(date);
}

/** The time of day of a moment, to the second (`14:05:09`). */
export function formatTime(value: Date | string): string {
	return formatDate(value, { timeStyle: 'medium' });
}

/** A number in the user's format. */
export function formatNumber(value: number, options?: Intl.NumberFormatOptions): string {
	return new Intl.NumberFormat(formatLocale(), options).format(value);
}

/** The decimal and group separators of the user's format ("," and "." in German). */
function separators(): { decimal: string; group: string } {
	const parts = new Intl.NumberFormat(formatLocale()).formatToParts(12345.6);
	const of = (type: string, otherwise: string) =>
		parts.find((part) => part.type === type)?.value ?? otherwise;
	return { decimal: of('decimal', '.'), group: of('group', ',') };
}

/** A number typed in the user's format as the API writes it (WG-K05), read as the server reads
 * a number a model wrote (`evidence.read_number`): "1.234,5" in German and "1,234.5" in English
 * are "1234.5". A separator groups only three digits after it: what only the other format fits
 * is read in that one ("12.50" in German is "12.50", not 1250), what both fit in the user's
 * ("1.234" in German is 1234). Text that fits neither comes back without its spaces, for the
 * API to refuse. */
export function readNumber(text: string): string {
	const { decimal } = separators();
	const bare = text.trim().replace(/\s/g, '');
	const sign = bare.startsWith('-') ? '-' : '';
	const digits = bare.slice(sign.length);
	const [own, other] = decimal === ',' ? [',', '.'] : ['.', ','];
	const read = notation(digits, own, `${other}'`) ?? notation(digits, other, `${own}'`);
	return read === null ? bare : sign + read;
}

/** `text` with `mark` as its decimal separator and thousands grouped by one of `groups` (one
 * kind in a number), as the API writes it; null if it does not fit that notation. */
function notation(text: string, mark: string, groups: string): string | null {
	const at = text.lastIndexOf(mark);
	const whole = at < 0 ? text : text.slice(0, at);
	const fraction = at < 0 ? '' : text.slice(at + 1);
	if (at >= 0 && (whole.includes(mark) || !/^\d+$/.test(fraction))) return null;
	if (at >= 0 && whole === '') return `0.${fraction}`; // ",5"
	const parts = whole.split(new RegExp(`[${groups.replace(/[\]\\^-]/g, '\\$&')}]`));
	const grouped = parts.length > 1;
	if (grouped && (parts[0].length > 3 || parts.slice(1).some((part) => part.length !== 3))) {
		return null;
	}
	if (grouped && new Set([...whole].filter((char) => groups.includes(char))).size > 1) {
		return null;
	}
	if (!parts.every((part) => /^\d+$/.test(part))) return null;
	return parts.join('') + (at >= 0 ? `.${fraction}` : '');
}

/** A number of the API ("1234.5") in the user's format for a field, without groups, so that
 * it reads as typed ("1234,5" in German). */
export function shownNumber(value: string): string {
	const { decimal } = separators();
	return decimal === '.' ? value : value.replace('.', decimal);
}

/** A share (0 to 1) as whole percent (`87 %`). */
export function formatPercent(value: number): string {
	return formatNumber(value, { style: 'percent', maximumFractionDigits: 0 });
}

/**
 * An amount of money; `amount` is the API's exact decimal text, `currency` an ISO 4217 code.
 * A currency the browser does not know as a code is written plainly after the amount.
 */
export function formatMoney(amount: string, currency: string): string {
	try {
		return new Intl.NumberFormat(formatLocale(), { style: 'currency', currency }).format(
			Number(amount)
		);
	} catch {
		return `${formatNumber(Number(amount), { minimumFractionDigits: 2 })} ${currency}`;
	}
}
