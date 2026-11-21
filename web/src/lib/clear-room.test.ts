import { afterEach, describe, expect, it } from 'vitest';
import css from '../app.css?raw';
import { keepClear } from './clear-room.svelte.ts';

const room = (edge: string) => document.documentElement.style.getPropertyValue(`--clear-${edge}`);

afterEach(() => {
	document.documentElement.style.removeProperty('--clear-top');
	document.documentElement.style.removeProperty('--clear-bottom');
});

describe('the room of the bars that stick (WZ-03)', () => {
	it('tells the document how much of each edge the bars take, the largest of them', () => {
		// The keyboard's target was scrolled just into view: under the header or a bar.
		const tools = keepClear('top', 112);
		const bar = keepClear('top', 140);
		const below = keepClear('bottom', 96.4);
		expect([room('top'), room('bottom')]).toEqual(['140px', '96px']);
		bar();
		expect(room('top')).toBe('112px');
		tools();
		below();
		// Nothing of a page left: the header alone, as the style sheet says.
		expect([room('top'), room('bottom')]).toEqual(['', '']);
	});

	it('is what the document scrolls a focused element clear of', () => {
		expect(css).toMatch(/scroll-padding-top:\s*calc\(var\(--clear-top, 4rem\)/);
		expect(css).toMatch(/scroll-padding-bottom:\s*calc\(var\(--clear-bottom, 0px\)/);
	});
});
