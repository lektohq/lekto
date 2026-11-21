import { render, screen } from '@testing-library/svelte';
import { toast } from 'svelte-sonner';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import appShell from './AppShell.svelte?raw';
import Loading from './Loading.svelte';
import OnDemand from './OnDemand.svelte';
import layout from '../../routes/(app)/+layout.svelte?raw';

const part = () => Promise.resolve({ default: Loading as never });

beforeEach(() => vi.useFakeTimers());
afterEach(() => {
	vi.useRealTimers();
	vi.restoreAllMocks();
});

describe('a part loaded when it is wanted (WP-04)', () => {
	it('is not loaded with the page, but as soon as something asks for it', async () => {
		const load = vi.fn(part);
		const { rerender } = render(OnDemand, { load, wanted: false });
		expect(load).not.toHaveBeenCalled();
		expect(screen.queryByRole('status')).toBeNull();
		await rerender({ load, wanted: true });
		expect(load).toHaveBeenCalledOnce();
		await vi.waitFor(() => expect(screen.getByRole('status')).toBeTruthy());
	});

	it('is loaded ahead once the page stands, so that the first opening does not wait', async () => {
		const load = vi.fn(part);
		const { rerender } = render(OnDemand, { load, wanted: false });
		await vi.advanceTimersByTimeAsync(3000);
		expect(load).toHaveBeenCalledOnce();
		await rerender({ load, wanted: true });
		expect(load).toHaveBeenCalledOnce();
	});

	it('says so when its file is gone (a tab from before an update), and tries again when asked', async () => {
		const failed = vi.spyOn(toast, 'error').mockImplementation(() => '');
		const load = vi
			.fn<typeof part>()
			.mockRejectedValueOnce(new TypeError('Failed to fetch dynamically imported module'))
			.mockImplementation(part);
		const { rerender } = render(OnDemand, { load, wanted: true });
		await vi.waitFor(() => expect(failed).toHaveBeenCalledWith(m.part_load_failed()));
		await rerender({ load, wanted: false });
		await rerender({ load, wanted: true });
		await vi.waitFor(() => expect(screen.getByRole('status')).toBeTruthy());
		expect(load).toHaveBeenCalledTimes(2);
	});

	it('is how the shell takes the Beam and the dialogs of the master data', () => {
		// Imported plainly, each page loaded both before its first picture: a third more code.
		expect(appShell).toContain("import('#lib/components/Beam.svelte')");
		expect(appShell).not.toMatch(/^\s*import Beam from/m);
		expect(layout).toContain("import('#lib/components/MasterDataDialogHost.svelte')");
		expect(layout).not.toMatch(/^\s*import MasterDataDialogHost from/m);
	});
});
