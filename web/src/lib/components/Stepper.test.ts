import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import Stepper from './Stepper.svelte';

const names = { label: 'Dokumente', previousLabel: 'Zurück', nextLabel: 'Weiter' };

describe('Stepper', () => {
	it('puts the arrows at its edge and the text on the other side', () => {
		const { container, unmount } = render(Stepper, {
			...names,
			text: 'Dokument 2 von 31',
			side: 'end',
			previous: '/a',
			next: '/c'
		});
		const nav = screen.getByRole('navigation', { name: 'Dokumente' });
		expect(nav.firstElementChild?.textContent).toBe('Dokument 2 von 31');
		expect(screen.getByRole('link', { name: 'Weiter' }).getAttribute('href')).toBe('/c');
		unmount();
		container.remove();
		render(Stepper, {
			...names,
			text: 'Dokument 2 von 31',
			side: 'start',
			previous: null,
			next: null
		});
		expect(screen.getByRole('navigation').lastElementChild?.textContent).toBe('Dokument 2 von 31');
	});

	it('keeps the arrow at the first and the last, disabled', async () => {
		const next = vi.fn();
		render(Stepper, { ...names, text: 'Dokument 1 von 2', side: 'start', previous: null, next });
		expect(screen.getByRole('button', { name: 'Zurück' })).toHaveProperty('disabled', true);
		await userEvent.click(screen.getByRole('button', { name: 'Weiter' }));
		expect(next).toHaveBeenCalledOnce();
	});
});
