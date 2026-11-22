import { render, waitFor } from '@testing-library/svelte';
import { toast } from 'svelte-sonner';
import { afterEach, describe, expect, it } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import Toaster from './sonner.svelte';

afterEach(() => toast.dismiss());

describe('the toaster (WE-12)', () => {
	it('names its region and the ✕ of a toast in the language of the UI', async () => {
		render(Toaster, { closeButton: true });
		toast.info('Gespeichert.');
		await waitFor(() => expect(document.querySelector('[data-sonner-toast]')).not.toBeNull());
		const region = document.querySelector('section[aria-label]');
		expect(region?.getAttribute('aria-label')?.startsWith(m.toast_region())).toBe(true);
		expect(
			document.querySelector('[data-sonner-toast] [data-close-button]')?.getAttribute('aria-label')
		).toBe(m.toast_close());
	});
});
