import { fireEvent, render, screen } from '@testing-library/svelte';
import { createRawSnippet } from 'svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import { TEXT_HINT } from '#lib/viewer/text-hint.ts';
import PageViewer from './PageViewer.svelte';
import { elapse, fakeTime } from '#lib/testing/time.ts';

// jsdom lays nothing out: the viewer gets a width and its paddings by hand.
let clientWidth: PropertyDescriptor | undefined;

beforeEach(() => {
	// Zooming keeps its place by scrolling the window, which jsdom does not do.
	vi.spyOn(window, 'scrollBy').mockImplementation(() => {});
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
	vi.restoreAllMocks();
	if (clientWidth) Object.defineProperty(HTMLElement.prototype, 'clientWidth', clientWidth);
});

const page = createRawSnippet(() => ({ render: () => '<span></span>' }));

describe('PageViewer', () => {
	it('names each page and says where the text of the pages stands (WZ-08)', () => {
		// The pages are images of the document: without names the region read as empty.
		const sizes = [1, 2, 3].map(() => ({ width: 600, height: 800 }));
		render(PageViewer, {
			props: { sizes, label: 'Pages of “Muster Versicherung”', page },
			context: new Map([[TEXT_HINT, () => m.pages_text_hint()]])
		});
		const pages = screen.getAllByRole('img');
		expect(pages.map((image) => image.getAttribute('aria-label'))).toEqual([
			m.pdf_page({ current: '1', total: '3' }),
			m.pdf_page({ current: '2', total: '3' }),
			m.pdf_page({ current: '3', total: '3' })
		]);
		const view = screen.getByRole('document');
		const hint = document.getElementById(view.getAttribute('aria-describedby') ?? '');
		expect(hint?.textContent).toBe(m.pages_text_hint());
	});

	it('says nothing of a text where nobody told it of one', () => {
		render(PageViewer, { sizes: [{ width: 600, height: 800 }], label: 'PDF', page });
		expect(screen.getByRole('document').hasAttribute('aria-describedby')).toBe(false);
	});

	it('zooms with + and − but leaves the browser its shortcuts with Ctrl, ⌘ or Alt', async () => {
		render(PageViewer, { sizes: [{ width: 600, height: 800 }], label: 'PDF', page });
		const view = screen.getByRole('document');
		// Named by the percent it shows, then by what it does (WC-08).
		const button = () =>
			screen.getByRole('button', {
				name: new RegExp(`^\\d+ %, .*${m.pdf_zoom_reset().slice(1)}$`)
			});
		const zoom = () => button().textContent?.trim();
		expect(
			button()
				.getAttribute('aria-label')
				?.startsWith(zoom() ?? 'none')
		).toBe(true);
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
		fakeTime(); // what reveals a place runs a frame or more later: a second passes at once
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
		await elapse(1000);
		expect(scroll).not.toHaveBeenCalled();
		dialog.remove();
	});
});
