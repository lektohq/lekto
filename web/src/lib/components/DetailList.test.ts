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

	it('shows two rows of one label: a field may be named like a built-in one', () => {
		const { container } = render(DetailList, {
			rows: [
				['Titel', 'Rechnung 12345'],
				['Titel', 'aus dem Feld'],
				['Kontakt', 'Muster Bäckerei']
			]
		});
		expect([...container.querySelectorAll('dt')].map((node) => node.textContent)).toEqual([
			'Titel',
			'Titel',
			'Kontakt'
		]);
		expect([...container.querySelectorAll('dd')].map((node) => node.textContent)).toEqual([
			'Rechnung 12345',
			'aus dem Feld',
			'Muster Bäckerei'
		]);
	});
});
