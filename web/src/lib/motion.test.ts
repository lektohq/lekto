// A scroll that code starts glides, or jumps for who asked for less motion (WZ-10).
import { afterEach, describe, expect, it, vi } from 'vitest';
import { reducedMotion, scrollBehavior } from './motion.ts';

const asks = (reduce: boolean) =>
	vi
		.spyOn(window, 'matchMedia')
		.mockImplementation(
			(query) => ({ matches: reduce && query.includes('reduce') }) as MediaQueryList
		);

afterEach(() => vi.restoreAllMocks());

describe('motion a script starts', () => {
	it('glides by default', () => {
		asks(false);
		expect(reducedMotion()).toBe(false);
		expect(scrollBehavior()).toBe('smooth');
	});

	it('jumps for who asked for less motion', () => {
		asks(true);
		expect(reducedMotion()).toBe(true);
		expect(scrollBehavior()).toBe('auto');
	});

	it('glides in a browser that cannot say', () => {
		vi.stubGlobal('matchMedia', undefined);
		expect(scrollBehavior()).toBe('smooth');
	});
});
