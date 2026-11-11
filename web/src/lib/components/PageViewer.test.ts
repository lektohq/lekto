import { fireEvent, render, screen } from '@testing-library/svelte';
import { createRawSnippet } from 'svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import PageViewer from './PageViewer.svelte';

// jsdom lays nothing out: the viewer gets a width and its paddings by hand.
let clientWidth: PropertyDescriptor | undefined;

beforeEach(() => {
	clientWidth = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'clientWidth');
	Object.defineProperty(HTMLElement.prototype, 'clientWidth', { configurable: true, value: 800 });
	vi.spyOn(window, 'getComputedStyle').mockReturnValue({
		paddingLeft: '12px',
		paddingRight: '12px',
		columnGap: '12px',
		// Finding a button by its name reads styles too.
		getPropertyValue: () => ''
	} as unknown as CSSStyleDeclaration);
	// Zooming looks for the page under the pointer.
	document.elementFromPoint ??= () => null;
	vi.stubGlobal(
		'IntersectionObserver',
		class {
			observe() {}
			unobserve() {}
			disconnect() {}
		}
	);
});

afterEach(() => {
	vi.unstubAllGlobals();
	vi.restoreAllMocks();
	if (clientWidth) Object.defineProperty(HTMLElement.prototype, 'clientWidth', clientWidth);
});

const page = createRawSnippet(() => ({ render: () => '<span></span>' }));

describe('PageViewer', () => {
	it('zooms with + and − but leaves the browser its shortcuts with Ctrl, ⌘ or Alt', async () => {
		render(PageViewer, { sizes: [{ width: 600, height: 800 }], label: 'PDF', page });
		const view = screen.getByRole('document');
		const zoom = () => screen.getByRole('button', { name: m.pdf_zoom_reset() }).textContent?.trim();
		const before = zoom();
		await fireEvent.keyDown(view, { key: '+', ctrlKey: true });
		await fireEvent.keyDown(view, { key: '-', metaKey: true });
		await fireEvent.keyDown(view, { key: '0', altKey: true });
		expect(zoom()).toBe(before);
		await fireEvent.keyDown(view, { key: '+' });
		expect(zoom()).not.toBe(before);
	});
	it('reveals a place asked for while the file still loads once its pages stand', async () => {
		const scroll = vi.spyOn(window, 'scrollBy').mockImplementation(() => {});
		const place = { page: 2, boxes: [{ x: 0.1, y: 0.5, width: 0.2, height: 0.05 }] };
		const { component, rerender } = render(PageViewer, {
			sizes: [],
			loading: true,
			label: 'PDF',
			page
		});
		component.reveal(place);
		expect(scroll).not.toHaveBeenCalled();
		await rerender({
			sizes: [
				{ width: 600, height: 800 },
				{ width: 600, height: 800 }
			],
			loading: false
		});
		await vi.waitFor(() => expect(scroll).toHaveBeenCalledOnce());
		// Revealed once: a later fit does not scroll there again.
		await rerender({ sizes: [{ width: 600, height: 800 }] });
		expect(scroll).toHaveBeenCalledOnce();
	});

	it('never scrolls the page behind a dialog to reveal a place (the Beam)', async () => {
		const scroll = vi.spyOn(window, 'scrollBy').mockImplementation(() => {});
		const dialog = document.body.appendChild(document.createElement('div'));
		dialog.setAttribute('role', 'dialog');
		const place = { page: 1, boxes: [{ x: 0.1, y: 0.5, width: 0.2, height: 0.05 }] };
		const { component, rerender } = render(PageViewer, {
			target: dialog,
			props: { sizes: [], loading: true, label: 'PDF', page }
		});
		component.reveal(place);
		await rerender({ sizes: [{ width: 600, height: 800 }], loading: false });
		await new Promise((resolve) => setTimeout(resolve, 50));
		expect(scroll).not.toHaveBeenCalled();
		dialog.remove();
	});
});
