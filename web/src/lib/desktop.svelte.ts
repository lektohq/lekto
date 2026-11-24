/**
 * Whether the window is as wide as a desktop: from Tailwind's `lg` (64rem) on, where the
 * document view fills the window and the processing tab shows the steps and the chosen one side
 * by side. Below it the steps are a list that opens one step at a time.
 */
import { ScreenQuery } from '#lib/screen-query.svelte.ts';

export const DESKTOP_QUERY = '(width >= 64rem)';

export const desktop = new ScreenQuery(DESKTOP_QUERY);

/** From Tailwind's `xl` (80rem) on, where the processing tab sets the runs beside the steps;
 * narrower, above them, so that the four columns of the steps keep the whole width. */
export const WIDE_DESKTOP_QUERY = '(width >= 80rem)';

export const wideDesktop = new ScreenQuery(WIDE_DESKTOP_QUERY);
