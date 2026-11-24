// The languages' strategy is given twice: to the Vite plugin and to the script "paraglide" that
// compiles the messages for svelte-check. Both must say the same (WK-K11).
import { describe, expect, it } from 'vitest';
import packageText from '../package.json?raw';
import config from '../vite.config.ts?raw';

describe('the strategy of the languages', () => {
	it('is the same for the Vite plugin and for the script "paraglide"', () => {
		const plugin = /strategy:\s*\[([^\]]*)\]/.exec(config)?.[1] ?? '';
		const inPlugin = [...plugin.matchAll(/'([^']+)'/g)].map((found) => found[1]);
		const script: string = JSON.parse(packageText).scripts.paraglide;
		const inScript = /--strategy ([\w ]+?)(?: --|$)/.exec(script)?.[1].split(' ');
		expect(inPlugin.length).toBeGreaterThan(0);
		expect(inScript).toEqual(inPlugin);
	});
});
