import { formatDate } from '#lib/i18n.ts';

/** The tabs of the page "System"; the first is shown without `?tab=` and for an unknown one. */
export const SYSTEM_TABS = [
	'automation',
	'classifier',
	'search',
	'jobs',
	'intake',
	'maintenance'
] as const;
export type SystemTab = (typeof SYSTEM_TABS)[number];

/** Tabs only admins see: the intake channels (Tobi, 04.11.2026). */
const ADMIN_TABS: readonly SystemTab[] = ['intake'];

/** The tabs a person sees. */
export function systemTabs(admin: boolean): readonly SystemTab[] {
	return admin ? SYSTEM_TABS : SYSTEM_TABS.filter((tab) => !ADMIN_TABS.includes(tab));
}

export function systemTab(params: Pick<URLSearchParams, 'get'>, admin: boolean): SystemTab {
	const tab = params.get('tab') ?? '';
	const tabs = systemTabs(admin);
	return (tabs as readonly string[]).includes(tab) ? (tab as SystemTab) : tabs[0];
}

/**
 * The label of a month on the history (`start`: its first day as ISO date): the short month name,
 * with the year when the history spans more than one (`withYear`): the charts tell months apart
 * by their label, and "Oct" alone names two in twenty months.
 */
export function monthLabel(start: string, withYear: boolean): string {
	return formatDate(
		`${start}T12:00:00`,
		withYear ? { month: 'short', year: '2-digit' } : { month: 'short' }
	);
}
