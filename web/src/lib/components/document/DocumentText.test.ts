import { render, screen, within } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, onTestFinished, vi } from 'vitest';
import { fakeApi } from '#lib/testing/api.ts';
import { events } from '#lib/events.svelte.ts';
import { m } from '#lib/paraglide/messages.js';
import DocumentText from './DocumentText.svelte';
import { streamEvents } from '#lib/testing/events.ts';
import { settled } from '#lib/testing/time.ts';

let answer: object = {};
let fetchMock = fakeApi();

const TEXT =
	'Gesamtbrutto (EBeschV)      6.767,00\nSteuer-Brutto, EZ           3.544,50\n\f\nSeite zwei';

beforeEach(() => {
	answer = { text: TEXT, offset: 0, total_length: TEXT.length, next_offset: null };
	fetchMock = fakeApi({ 'GET /api/v1/documents/doc-1/text': () => answer });
	vi.stubGlobal('fetch', fetchMock);
});

afterEach(() => {
	vi.restoreAllMocks();
	events.stop();
});

/** Page `number` of the text, once it is drawn. */
function pageOf(number: number): Promise<HTMLElement> {
	return vi.waitFor(() => {
		const found = document.querySelector<HTMLElement>(`[data-page="${number}"]`);
		expect(found).not.toBeNull();
		return found!;
	});
}

describe('DocumentText', () => {
	it('reads the text again only when its node has read it again', async () => {
		// Issue #75: of a run's events only the text's node changes the text.
		const send = streamEvents();
		const completed = (node: string) =>
			send('document.node_completed', { document_id: 'doc-1', node, run: 1, outcome: 'ok' });
		render(DocumentText, { documentId: 'doc-1' });
		await pageOf(1);
		for (const node of ['ocr', 'pages', 'signal_llm', 'judge']) completed(node);
		expect(fetchMock).toHaveBeenCalledTimes(1);
		completed('parse');
		expect(fetchMock).toHaveBeenCalledTimes(2);
	});

	it('shows the text as it is set, page by page', async () => {
		render(DocumentText, { documentId: 'doc-1' });
		const first = await pageOf(1);
		const second = await pageOf(2);
		// Columns stay where they are set: no Markdown, no collapsed spaces.
		expect(first.querySelector('pre')?.textContent).toBe(
			'Gesamtbrutto (EBeschV)      6.767,00\nSteuer-Brutto, EZ           3.544,50'
		);
		expect(within(second).getByText('Seite zwei')).toBeTruthy();
		// The text alone: no switch to its structure any more.
		expect(screen.queryByRole('group')).toBeNull();
	});

	it('asks for no text before the document has it', async () => {
		render(DocumentText, { documentId: 'doc-1', hasText: false });
		await settled();
		expect(fetchMock).not.toHaveBeenCalled();
		expect(document.querySelector('[data-page]')).toBeNull();
		expect(screen.queryByText(m.loading())).toBeNull();
	});

	it('marks what it is given, and scrolls there when asked', async () => {
		const scrolled = vi.fn();
		// jsdom has none: given for this test, gone after it however it ends.
		Element.prototype.scrollIntoView = scrolled;
		onTestFinished(() => {
			delete (Element.prototype as Partial<Element>).scrollIntoView;
		});
		const view = render(DocumentText, {
			documentId: 'doc-1',
			marks: [{ start: 14, end: 21 }]
		});
		await pageOf(1);
		expect(document.querySelector('mark[data-mark]')?.textContent).toBe('EBeschV');
		await view.component.revealMark();
		expect(scrolled).toHaveBeenCalled();
	});

	it('tells the page in the upper third of what is seen', async () => {
		// Page 1 has gone up, page 2 starts above the line a third down the window, page 3 below.
		const tops: Record<string, number> = { '1': -500, '2': 100, '3': 900 };
		vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(function (
			this: Element
		) {
			const page = (this as HTMLElement).dataset?.page;
			const top = page ? tops[page] : 0;
			return { top, bottom: page ? top + 400 : 800, left: 0, right: 400 } as DOMRect;
		});
		answer = {
			text: 'eins\n\f\nzwei\n\f\ndrei',
			offset: 0,
			total_length: 17,
			next_offset: null
		};
		const onpage = vi.fn();
		render(DocumentText, { documentId: 'doc-1', onpage });
		await pageOf(3);
		window.dispatchEvent(new Event('scroll'));
		await vi.waitFor(() => expect(onpage).toHaveBeenLastCalledWith(2, 3));
	});

	it('follows the scrolling once a frame, and not while it is hidden', async () => {
		answer = {
			text: 'eins\n\f\nzwei\n\f\ndrei',
			offset: 0,
			total_length: 17,
			next_offset: null
		};
		const onpage = vi.fn();
		render(DocumentText, { documentId: 'doc-1', onpage });
		await pageOf(3);
		await new Promise((resolve) => requestAnimationFrame(resolve));
		const measured = vi.spyOn(Element.prototype, 'getBoundingClientRect');
		for (let step = 0; step < 5; step++) window.dispatchEvent(new Event('scroll'));
		await new Promise((resolve) => requestAnimationFrame(resolve));
		expect(measured.mock.calls.length).toBeLessThanOrEqual(4); // the box and its three pages
		// Hidden (another tab of the page), everything measures nothing: it is no last page.
		Element.prototype.checkVisibility = () => false;
		onTestFinished(() => {
			delete (Element.prototype as Partial<Element>).checkVisibility;
		});
		onpage.mockClear();
		window.dispatchEvent(new Event('scroll'));
		await new Promise((resolve) => requestAnimationFrame(resolve));
		expect(onpage).not.toHaveBeenCalledWith(3, 3);
	});

	it('marks the quotes it is given where they stand, however their spaces fall', async () => {
		render(DocumentText, {
			documentId: 'doc-1',
			marks: [{ start: 14, end: 21 }],
			quotes: ['Steuer-Brutto, EZ 3.544,50', 'nicht im Text']
		});
		await pageOf(1);
		const marked = [...document.querySelectorAll('mark[data-mark]')].map(
			(mark) => mark.textContent
		);
		expect(marked).toEqual(['EBeschV', 'Steuer-Brutto, EZ           3.544,50']);
	});
});
