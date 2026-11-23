import { describe, expect, it, vi } from 'vitest';

const attempts = vi.hoisted(() => ({ count: 0 }));
vi.mock('#lib/icons/curated-modules.ts', () => ({
	curatedModule: () => () => {
		attempts.count += 1;
		return attempts.count === 1
			? Promise.reject(new TypeError('Failed to fetch dynamically imported module'))
			: Promise.resolve({ default: 'the icon' });
	}
}));

const { loadIcon } = await import('./load.ts');

describe('loading an icon', () => {
	it('tries again after a load that failed, instead of keeping nothing (WG-K04)', async () => {
		expect(await loadIcon('receipt')).toBeNull(); // the network dropped
		expect(await loadIcon('receipt')).toBe('the icon');
		expect(await loadIcon('receipt')).toBe('the icon'); // and then kept
		expect(attempts.count).toBe(2);
	});
});
