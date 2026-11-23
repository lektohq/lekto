// A stand-in for `$app/state` whose `page` a test moves with `goTo` of `page-state.svelte.ts`:
// `vi.mock('$app/state', () => import('#lib/testing/app-state.ts'))`.
export { testPage as page } from './page-state.svelte.ts';
