import { afterEach, describe, expect, it } from 'vitest';
import { centre, sideways, SIDEWAYS_FADE } from './sideways.ts';

/** A row of `scrollWidth` in a room of `clientWidth`, which jsdom does not lay out. */
function row(scrollWidth: number, clientWidth: number) {
	const room = document.createElement('div');
	Object.defineProperties(room, {
		scrollWidth: { value: scrollWidth, configurable: true },
		clientWidth: { value: clientWidth, configurable: true }
	});
	room.innerHTML = '<a>one</a><a aria-current="page">two</a>';
	document.body.append(room);
	return room;
}

const marks = (room: HTMLElement) => [
	room.hasAttribute('data-more-start'),
	room.hasAttribute('data-more-end')
];

afterEach(() => document.body.replaceChildren());

describe('a row that scrolls sideways (WC-12)', () => {
	it('marks the edges that have more behind them, as it scrolls', () => {
		const room = row(300, 100);
		const stop = sideways(room) as () => void;
		expect(marks(room)).toEqual([false, true]);
		room.scrollLeft = 80;
		room.dispatchEvent(new Event('scroll'));
		expect(marks(room)).toEqual([true, true]);
		room.scrollLeft = 200;
		room.dispatchEvent(new Event('scroll'));
		expect(marks(room)).toEqual([true, false]);
		stop();
		room.scrollLeft = 0;
		room.dispatchEvent(new Event('scroll'));
		expect(marks(room)).toEqual([true, false]);
	});

	it('marks nothing where all of it fits', () => {
		const room = row(100, 100);
		sideways(room);
		expect(marks(room)).toEqual([false, false]);
	});

	it('brings the chosen one to the middle, and marks the edges anew', () => {
		const room = row(300, 100);
		sideways(room);
		const chosen = room.querySelector<HTMLElement>('[aria-current="page"]')!;
		Object.defineProperties(chosen, {
			offsetLeft: { value: 150 },
			offsetWidth: { value: 40 }
		});
		centre(room, '[aria-current="page"]');
		// 150 − (100 − 40) / 2
		expect(room.scrollLeft).toBe(120);
		expect(marks(room)).toEqual([true, true]);
		centre(room, '[aria-pressed="true"]');
		expect(room.scrollLeft).toBe(120);
	});

	it('fades each marked edge', () => {
		expect(SIDEWAYS_FADE).toContain('data-more-end:[mask-image:');
		expect(SIDEWAYS_FADE).toContain('data-more-start:[mask-image:');
	});
});
