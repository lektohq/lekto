import { vi } from 'vitest';

// A stand-in for `$app/navigation` whose `goto` keeps the states of the history entries, beside
// `app-state.ts`: `vi.mock('$app/navigation', () => import('#lib/testing/app-navigation.ts'))`.
export { fakeGoto as goto } from './page-state.svelte.ts';
export const beforeNavigate = vi.fn();
