import { fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import { goTo, testPage } from '#lib/testing/page-state.svelte.ts';
import { uploads } from '#lib/upload.svelte.ts';
import Page from './+page.svelte';

const goto = vi.hoisted(() => vi.fn(async () => {}));
vi.mock('$app/navigation', () => ({ goto }));
vi.mock('$app/state', () => import('#lib/testing/app-state.ts'));
const shared = vi.hoisted(() => ({
	readShared: vi.fn(async (): Promise<File[]> => []),
	forgetShared: vi.fn(async () => {}),
	forgetSharedFile: vi.fn(async () => {})
}));
vi.mock('#lib/shared-files.ts', () => shared);

const ID = '0b0e7c1e-2f2a-4d67-9a43-6f1f0c2d9e11';
const pdf = (name: string) => new File(['%PDF-1.7'], name, { type: 'application/pdf' });

/** Let what waits on promises run, and `ms` of the page's clock pass. */
const pass = (ms = 0) => vi.advanceTimersByTimeAsync(ms);
const uploadButton = () => screen.getByRole('button', { name: m.upload_title() });

describe('the page of a share', () => {
	let add: ReturnType<typeof vi.spyOn>;

	beforeEach(() => {
		vi.useFakeTimers();
		add = vi.spyOn(uploads, 'add').mockImplementation(() => {});
		shared.readShared.mockResolvedValue([pdf('Rechnung.pdf'), pdf('Rechnung.pdf')]);
		goTo(`/ui/share?id=${ID}`);
	});

	afterEach(() => {
		vi.useRealTimers();
		vi.restoreAllMocks();
		goto.mockClear();
		shared.readShared.mockReset();
		shared.forgetShared.mockClear();
		shared.forgetSharedFile.mockClear();
	});

	it('shows the shared files and uploads nothing by itself', async () => {
		render(Page);
		await pass(60_000);

		// Two files of one name are two rows.
		expect(screen.getAllByText('Rechnung.pdf')).toHaveLength(2);
		expect(shared.readShared).toHaveBeenCalledWith(ID);
		expect(add).not.toHaveBeenCalled();
		expect(shared.forgetShared).not.toHaveBeenCalled();
		expect(goto).not.toHaveBeenCalled();
		expect(testPage.url.searchParams.get('id')).toBe(ID);
	});

	it('uploads on "Hochladen" and goes to the inbox; a file leaves the device with its result (WM-06)', async () => {
		const note = new File(['x'], 'notes.txt', { type: 'text/plain' });
		const [good, broken] = [pdf('Rechnung.pdf'), pdf('Mahnung.pdf')];
		shared.readShared.mockResolvedValue([good, broken, note]);
		render(Page);
		await pass(1000);
		await fireEvent.click(uploadButton());
		await pass();

		expect(add).toHaveBeenCalledTimes(1);
		const [intake, options] = add.mock.calls[0];
		expect(intake.files.map((entry: { name: string }) => entry.name)).toEqual([
			'Rechnung.pdf',
			'Mahnung.pdf'
		]);
		expect(goto).toHaveBeenCalledWith('/ui/inbox', { replaceState: true });
		// Nothing is gone yet but what the upload does not take: its result is known.
		expect(shared.forgetShared).not.toHaveBeenCalled();
		expect(shared.forgetSharedFile.mock.calls).toEqual([[note]]);

		// Uploaded: gone. Failed: it stays, and the inbox's list leads back to this share.
		options.settled(good, 'uploaded');
		options.settled(broken, 'failed');
		expect(shared.forgetSharedFile.mock.calls).toEqual([[note], [good]]);
		expect(options.again).toBe(`/ui/share?id=${ID}`);
	});

	it('discards without an upload', async () => {
		render(Page);
		await pass();
		await fireEvent.click(screen.getByRole('button', { name: m.share_discard() }));
		await pass();

		expect(add).not.toHaveBeenCalled();
		expect(shared.forgetShared).toHaveBeenCalledWith(ID);
		expect(goto).toHaveBeenCalledWith('/ui/inbox', { replaceState: true });
	});

	it('does not count "Hochladen" before the page was in front for a second', async () => {
		render(Page);
		await pass(999);
		expect(uploadButton().getAttribute('aria-disabled')).toBe('true');
		await fireEvent.click(uploadButton());
		await pass();
		expect(add).not.toHaveBeenCalled();

		await pass(1);
		expect(uploadButton().getAttribute('aria-disabled')).toBe('false');
	});

	it('holds "Hochladen" again whenever the page comes to the front', async () => {
		render(Page);
		await pass(1000);

		// Another window was in front; the click that brings this one up must not upload.
		window.dispatchEvent(new Event('blur'));
		window.dispatchEvent(new Event('focus'));
		await pass(500);
		await fireEvent.click(uploadButton());
		await pass();
		expect(add).not.toHaveBeenCalled();

		await pass(500);
		await fireEvent.click(uploadButton());
		await pass();
		expect(add).toHaveBeenCalledTimes(1);
	});

	it('uploads once, however often "Hochladen" is pressed', async () => {
		render(Page);
		await pass(1000);
		await fireEvent.click(uploadButton());
		await fireEvent.click(uploadButton());
		await pass();

		expect(add).toHaveBeenCalledTimes(1);
	});

	it('says that nothing waits for a share that is gone, and drops its id', async () => {
		shared.readShared.mockResolvedValue([]);
		render(Page);
		await pass();

		expect(screen.getByText(m.share_missing())).toBeTruthy();
		expect(screen.queryByRole('button', { name: m.upload_title() })).toBeNull();
		expect(goto).toHaveBeenCalledWith('/ui/share', { replaceState: true });
	});

	it('reads nothing for an id that is none', async () => {
		goTo('/ui/share?id=../../etc');
		render(Page);
		await pass();

		expect(shared.readShared).not.toHaveBeenCalled();
		expect(screen.getByText(m.share_missing())).toBeTruthy();
	});
});
