/**
 * Whether the window is as wide as a desktop: from Tailwind's `lg` (64rem) on, where the
 * document view fills the window and the processing tab shows the steps and the chosen one side
 * by side. Below it the steps are a list that opens one step at a time.
 */
import { ScreenQuery } from '#lib/screen-query.svelte.ts';

export const DESKTOP_QUERY = '(width >= 64rem)';

export const desktop = new ScreenQuery(DESKTOP_QUERY);
