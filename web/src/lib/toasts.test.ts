import { afterEach, describe, expect, it } from 'vitest';
import { inToast, TOAST_CLASS, TOAST_CLOSE_CLASS } from './toasts.ts';

afterEach(() => document.body.replaceChildren());

describe('toasts above a layer', () => {
	it('knows a tap on a toast from one on the page (WM-02)', () => {
		document.body.innerHTML =
			'<main><button id="page">x</button></main>' +
			'<section><ol data-sonner-toaster><li data-sonner-toast><button id="toast">y</button></li></ol></section>';
		expect(inToast(document.getElementById('toast'))).toBe(true);
		expect(inToast(document.getElementById('page'))).toBe(false);
		expect(inToast(null)).toBe(false);
		expect(inToast(document)).toBe(false);
	});

	it('lets a toast take the pointer an open layer took from the page', () => {
		expect(TOAST_CLASS.split(' ')).toContain('pointer-events-auto');
	});

	it('gives the ✕ of a toast a hit area, a finger wide on a phone (WE-04)', () => {
		// 20 px as drawn: 2 px around it make 24, 12 px make 44.
		expect(TOAST_CLOSE_CLASS.split(' ')).toEqual(
			expect.arrayContaining(['after:absolute', 'after:-inset-0.5', 'max-sm:after:-inset-3'])
		);
	});
});
