/**
 * Whether the window is as narrow as a phone: below Tailwind's `sm` (40rem). Master data take
 * their phone layout there: rows that open the editor as a whole, editors on the full screen,
 * pickers as bottom sheets.
 */
import { ScreenQuery } from '#lib/screen-query.svelte.ts';

export const PHONE_QUERY = '(width < 40rem)';

export const phone = new ScreenQuery(PHONE_QUERY);
