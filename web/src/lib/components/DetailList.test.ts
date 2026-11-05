import { render } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import DetailList from './DetailList.svelte';

describe('a detail list', () => {
	it('names each fact by its label, in order, in a definition list', () => {
		const { container } = render(DetailList, {
			rows: [
				['Von', 'Stadtwerke <rechnung@stadtwerke.example>'],
				['Betreff', 'Ihre Rechnung']
			],
			class: 'px-1 pb-1'
		});
		const list = container.querySelector('dl');
		expect(list?.className).toContain('px-1 pb-1');
		expect([...list!.querySelectorAll('dt')].map((node) => node.textContent)).toEqual([
			'Von',
			'Betreff'
		]);
		expect([...list!.querySelectorAll('dd')].map((node) => node.textContent)).toEqual([
			'Stadtwerke <rechnung@stadtwerke.example>',
			'Ihre Rechnung'
		]);
	});
});
