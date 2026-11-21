import { render, screen, waitFor } from '@testing-library/svelte';
import { createRawSnippet } from 'svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import PhoneSheet from './PhoneSheet.svelte';

const close = createRawSnippet(() => ({
	render: () => '<button type="button">Schließen</button>'
}));
const children = createRawSnippet(() => ({ render: () => '<p>Was es anbietet</p>' }));

function sheet() {
	const onOpenChange = vi.fn();
	render(PhoneSheet, { open: true, title: 'Kontakt wählen', onOpenChange, close, children });
	const dialog = screen.getByRole('dialog', { name: 'Kontakt wählen' });
	// The handle and the title row: what a finger pulls.
	const head = dialog.querySelector('[role="presentation"]') as HTMLElement;
	return { onOpenChange, dialog, head };
}

/** A pull of the head by `distance` px, `ms` long: the clock moves between the events. */
function pull(target: Element, distance: number, ms = 400) {
	const fire = (type: string, y: number) =>
		target.dispatchEvent(new PointerEvent(type, { bubbles: true, isPrimary: true, clientY: y }));
	fire('pointerdown', 100);
	vi.advanceTimersByTime(ms / 2);
	fire('pointermove', 100 + distance / 2);
	vi.advanceTimersByTime(ms / 2);
	fire('pointermove', 100 + distance);
	fire('pointerup', 100 + distance);
}

// Time as events see it is faked; timers run, so that the sheet can leave.
beforeEach(() => vi.useFakeTimers({ toFake: ['Date', 'performance'] }));
afterEach(() => vi.useRealTimers());

describe('PhoneSheet', () => {
	it('takes the focus itself when it opens: no field, and not left behind it (WZ-02)', async () => {
		// The focus stayed on the button behind the modal sheet: Tab went over covered buttons
		// of the page first, and a screen reader did not start in the dialog.
		const field = createRawSnippet(() => ({ render: () => '<input aria-label="Suche" />' }));
		const opener = document.createElement('button');
		document.body.append(opener);
		opener.focus();
		render(PhoneSheet, { open: true, title: 'Kontakt wählen', close, children: field });
		const dialog = screen.getByRole('dialog', { name: 'Kontakt wählen' });
		await waitFor(() => expect(document.activeElement).toBe(dialog));
		// Not the field: the keyboard of a phone waits for a tap.
		expect(document.activeElement).not.toBe(screen.getByLabelText('Suche'));
		expect(dialog.getAttribute('tabindex')).toBe('-1');
		opener.remove();
	});

	it('closes when its head is pulled down far enough', async () => {
		const { onOpenChange, dialog, head } = sheet();
		pull(head, 160);
		// It slides out on its own; the closing animation would carry it back up.
		await waitFor(() => expect(dialog.getAttribute('style')).toContain('animation: none'));
		await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
		await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
	});

	it('closes when flicked down, however short', async () => {
		const { onOpenChange, head } = sheet();
		pull(head, 40, 40);
		await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false));
	});

	it('springs back from a short, slow pull', async () => {
		const { onOpenChange, dialog, head } = sheet();
		pull(head, 40, 800);
		await new Promise((resolve) => setTimeout(resolve, 300));
		expect(onOpenChange).not.toHaveBeenCalled();
		expect(dialog.style.transform).toBe('');
		expect(screen.getByRole('dialog')).toBe(dialog);
	});

	it('leaves a tap on its close button to the button', async () => {
		const { onOpenChange } = sheet();
		pull(screen.getByRole('button', { name: 'Schließen' }), 160);
		await new Promise((resolve) => setTimeout(resolve, 300));
		expect(onOpenChange).not.toHaveBeenCalled();
	});
});
