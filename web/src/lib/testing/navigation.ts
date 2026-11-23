import { vi } from 'vitest';

/**
 * A stand-in for `$app/navigation` in a test that only wants to see where a component goes:
 * `vi.mock('$app/navigation', () => import('#lib/testing/navigation.ts'))`, then
 * `vi.mocked(goto)` on the import from `$app/navigation`. A test that follows the history
 * entries takes `fakeGoto` of `page-state.svelte.ts` instead.
 */
export const goto = vi.fn();
export const beforeNavigate = vi.fn();
export const afterNavigate = vi.fn();
