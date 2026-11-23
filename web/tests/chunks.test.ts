// How the build splits the app's code (`vite-chunks.js`).
import { describe, expect, it } from 'vitest';
import house from '@lucide/svelte/icons/house?url';
import { codeSplitting, ICON } from '../vite-chunks.js';

describe('the chunks of the build', () => {
	// Each icon the app imports was a file of its own, nearly half of the small files a page
	// loaded at first (WP-05).
	it('puts the icons the app imports in one chunk', () => {
		const icons = codeSplitting().groups.find((group) => group.name === 'icons');
		expect(house).toMatch(ICON);
		expect(icons?.test).toBe(ICON);
	});

	// The picker's 1,866 icons load when shown (`lib/icons/lucide.ts`): in that chunk, every page
	// would load them all.
	it('leaves the icons loaded on demand out', () => {
		const icons = codeSplitting().groups.find((group) => group.name === 'icons');
		expect(icons?.tags).toEqual(['$initial']);
	});
});
