import Monitor from '@lucide/svelte/icons/monitor';
import Moon from '@lucide/svelte/icons/moon';
import Sun from '@lucide/svelte/icons/sun';
import { m } from '#lib/paraglide/messages.js';

/** The appearances to choose, once for the menu (`ThemeChoices`) and the phone's sheet
 * (`AppShell`): light, dark or as the system. */
export const THEME_OPTIONS = [
	{ value: 'light', label: m.theme_light, icon: Sun },
	{ value: 'dark', label: m.theme_dark, icon: Moon },
	{ value: 'system', label: m.theme_system, icon: Monitor }
] as const;

export type Theme = (typeof THEME_OPTIONS)[number]['value'];
