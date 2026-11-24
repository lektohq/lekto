import { render } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import PageImage from './PageImage.svelte';
import { settled } from '#lib/testing/time.ts';

describe('PageImage', () => {
	// A rejection left unhandled fails the run (vitest reports it as an error).
	it('keeps the placeholder when a file to be added cannot be drawn (WA-K16)', async () => {
		const draw = vi.fn(() => Promise.reject(new Error('not an image')));
		vi.stubGlobal('createImageBitmap', draw);
		const onsize = vi.fn();
		const { container } = render(PageImage, { src: 'data:image/png;base64,AAAA', onsize });
		await vi.waitFor(() => expect(draw).toHaveBeenCalled());
		await settled(draw);
		expect(onsize).not.toHaveBeenCalled();
		expect(container.querySelector('canvas')?.getAttribute('width')).toBe('3');
	});
});
