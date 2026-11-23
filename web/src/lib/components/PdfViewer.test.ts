import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { BASE } from '#lib/base.ts';
import { m } from '#lib/paraglide/messages.js';
import { pdfjsAssets } from '../../../vite-pdfjs.js';
import PdfViewer from './PdfViewer.svelte';

// pdf.js needs a worker and a canvas; the test watches only how a document is opened and
// dropped.
const pdfjs = vi.hoisted(() => ({
	getDocument: vi.fn(),
	GlobalWorkerOptions: { workerSrc: '' }
}));
vi.mock('pdfjs-dist/legacy/build/pdf.mjs', () => pdfjs);
vi.mock('pdfjs-dist/legacy/build/pdf.worker.min.mjs?url', () => ({ default: 'worker.js' }));

function deferred<T>() {
	let resolve!: (value: T) => void;
	const promise = new Promise<T>((done) => (resolve = done));
	return { promise, resolve };
}

function task() {
	const opened = deferred<{ numPages: number }>();
	return {
		promise: opened.promise,
		destroy: vi.fn(async () => {}),
		open: () => opened.resolve({ numPages: 0 })
	};
}

const settle = () => new Promise((resolve) => setTimeout(resolve, 0));
const SOURCES = ['/api/v1/documents/d1/archive'];

/** The files the build serves under `pdfjs/` (`vite-pdfjs.js`). */
function servedFiles(): string[] {
	const files: string[] = [];
	const plugin = pdfjsAssets() as unknown as {
		generateBundle(this: { emitFile(file: { fileName: string }): void }): void;
	};
	plugin.generateBundle.call({ emitFile: ({ fileName }) => files.push(`${BASE}/${fileName}`) });
	return files;
}

beforeEach(() => {
	pdfjs.getDocument.mockReset();
});

describe('PdfViewer', () => {
	it('opens no document when the viewer closed while the file was on its way', async () => {
		const download = deferred<Response>();
		vi.stubGlobal(
			'fetch',
			vi.fn(() => download.promise)
		);
		const { unmount } = render(PdfViewer, { sources: SOURCES, label: 'PDF' });
		unmount();
		download.resolve(new Response(new Uint8Array([1, 2, 3])));
		await settle();
		expect(pdfjs.getDocument).not.toHaveBeenCalled();
	});

	it('drops a document that finished opening after the viewer closed', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => new Response(new Uint8Array([1, 2, 3])))
		);
		const loading = task();
		pdfjs.getDocument.mockReturnValue(loading);
		const { unmount } = render(PdfViewer, { sources: SOURCES, label: 'PDF' });
		await vi.waitFor(() => expect(pdfjs.getDocument).toHaveBeenCalledOnce());
		unmount();
		loading.open();
		await settle();
		expect(loading.destroy).toHaveBeenCalled();
	});

	// Without the profile, pdf.js reckons CMYK colours (print files) roughly: they shift (WK-02).
	it('hands pdf.js the CMYK profile with the decoders, fonts and maps, each one served', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => new Response(new Uint8Array([1, 2, 3])))
		);
		pdfjs.getDocument.mockReturnValue(task());
		render(PdfViewer, { sources: SOURCES, label: 'PDF' });
		await vi.waitFor(() => expect(pdfjs.getDocument).toHaveBeenCalledOnce());
		const options = pdfjs.getDocument.mock.calls[0][0] as Record<string, unknown>;
		expect(options.iccUrl).toBe(`${BASE}/pdfjs/iccs/`);
		const served = servedFiles();
		expect(served).toContain(`${BASE}/pdfjs/iccs/CGATS001Compat-v2-micro.icc`);
		const urls = Object.entries(options).filter(([key]) => key.endsWith('Url'));
		expect(urls).toHaveLength(4);
		for (const [key, url] of urls) {
			expect(
				served.some((file) => file.startsWith(url as string)),
				key
			).toBe(true);
		}
	});

	it('says in the reader’s language that a file cannot be shown, and reads it again on request (WC-09)', async () => {
		const fetchMock = vi.fn(async () => new Response(new Uint8Array([1, 2, 3])));
		vi.stubGlobal('fetch', fetchMock);
		// What pdf.js says of a file that is no PDF.
		pdfjs.getDocument.mockReturnValue({
			promise: Promise.reject(new Error('Invalid PDF structure.')),
			destroy: vi.fn(async () => {})
		});
		render(PdfViewer, { sources: SOURCES, label: 'PDF' });
		expect(await screen.findByText(m.pdf_unreadable())).toBeTruthy();
		expect(screen.queryByText(/Invalid PDF structure/)).toBeNull();
		await userEvent.click(screen.getByRole('button', { name: m.retry() }));
		await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
	});

	it('says that the server is not reached as everywhere, and that no file is there (WC-09)', async () => {
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => {
				throw new TypeError('Failed to fetch');
			})
		);
		const lost = render(PdfViewer, { sources: SOURCES, label: 'PDF' });
		expect(await screen.findByText(m.error_network())).toBeTruthy();
		expect(screen.queryByText(/Failed to fetch/)).toBeNull();
		lost.unmount();
		vi.stubGlobal(
			'fetch',
			vi.fn(async () => new Response(null, { status: 404 }))
		);
		render(PdfViewer, { sources: SOURCES, label: 'PDF' });
		expect(await screen.findByText(m.pdf_missing())).toBeTruthy();
	});
});
