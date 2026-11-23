import { render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { components } from '#lib/api/schema.ts';
import TagPickerList from './TagPickerList.svelte';

type Tag = components['schemas']['TagOut'];

const topic = (id: string, name: string) =>
	({ id, name, path: [name], scope: 'topic', parent_id: null }) as unknown as Tag;

describe('TagPickerList', () => {
	it('tells a topic clicked once, not again by the change of its radio (WC-K13)', async () => {
		const onchange = vi.fn();
		const onpicked = vi.fn();
		render(TagPickerList, {
			title: 'Themen',
			scope: 'topic',
			tags: [topic('t1', 'Wohnung'), topic('t2', 'Auto')],
			selected: [],
			onchange,
			onpicked,
			single: true
		});
		await userEvent.setup().click(screen.getByText('Auto'));
		expect(onchange.mock.calls).toEqual([[['t2']]]);
		expect(onpicked).toHaveBeenCalledTimes(1);
	});
});
