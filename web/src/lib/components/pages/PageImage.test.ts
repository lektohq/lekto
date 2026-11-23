import { render } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';
import PageImage from './PageImage.svelte';

describe('PageImage', () => {
	// A rejection left unhandled fails the run (vitest reports it as an error).
	it('keeps the placeholder when a file to be added cannot be drawn (WA-K16)', async () => {
		vi.stubGlobal(
			'createImageBitmap',
			vi.fn(() => Promise.reject(new Error('not an image')))
		);
		const onsize = vi.fn();
		const { container } = render(PageImage, { src: 'data:image/png;base64,AAAA', onsize });
		await new Promise((resolve) => setTimeout(resolve, 20));
		expect(onsize).not.toHaveBeenCalled();
		expect(container.querySelector('canvas')?.getAttribute('width')).toBe('3');
	});
});
