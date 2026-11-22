import { render } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import { goTo } from '#lib/testing/page-state.svelte.ts';
import { signIn } from '#lib/testing/session.ts';
import Page from './+page.svelte';

// The tabs stand in by a stub; each says when its code is loaded.
const { loaded, stub } = vi.hoisted(() => {
	const loaded = new Set<string>();
	const stub = async (name: string) => {
		loaded.add(name);
		return import('#lib/testing/Stub.svelte');
	};
	return { loaded, stub };
});
vi.mock('$app/state', () => import('#lib/testing/app-state.ts'));
vi.mock('#lib/components/system/AutomationTab.svelte', () => stub('automation'));
vi.mock('#lib/components/system/ClassifierTab.svelte', () => stub('classifier'));
vi.mock('#lib/components/system/JobsTab.svelte', () => stub('jobs'));
vi.mock('#lib/components/system/SearchTab.svelte', () => stub('search'));
vi.mock('#lib/components/system/IntakeTab.svelte', () => stub('intake'));
// It asks the API for the version; not this test's matter.
vi.mock('#lib/components/system/UpdateNotice.svelte', () => import('#lib/testing/Stub.svelte'));

describe('the page "System"', () => {
	// The page opens on the jobs; the charts of automation and classifier (LayerChart, d3: some
	// 300 KB) came with it all the same (WP-06).
	it('loads the code of the tabs with charts when they are shown', async () => {
		signIn('admin');
		goTo('/ui/system');
		const { container } = render(Page);
		expect(container.querySelector('[data-stub]')).not.toBeNull();
		expect(loaded).not.toContain('automation');
		expect(loaded).not.toContain('classifier');

		goTo('/ui/system?tab=automation');
		await vi.waitFor(() => expect(loaded).toContain('automation'));
		expect(loaded).not.toContain('classifier');
		goTo('/ui/system?tab=classifier');
		await vi.waitFor(() => expect(loaded).toContain('classifier'));
	});
});
