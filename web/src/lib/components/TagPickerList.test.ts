import { fireEvent, render, screen } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { components } from '#lib/api/schema.ts';
import TagPickerList from './TagPickerList.svelte';

type Tag = components['schemas']['TagOut'];

const topic = (id: string, name: string) =>
	({ id, name, path: [name], scope: 'topic', parent_id: null }) as unknown as Tag;

describe('TagPickerList', () => {
	const tags = [topic('t1', 'Wohnung'), topic('t2', 'Auto')];

	it('tells a topic clicked once, not again by the change of its radio (WC-K13)', async () => {
		const onpicked = vi.fn();
		// As its callers do: what it tells is chosen at once.
		const onchange = vi.fn((next: string[]) => void rerender({ selected: next }));
		const { rerender } = render(TagPickerList, {
			title: 'Themen',
			scope: 'topic',
			tags,
			selected: [],
			onchange,
			onpicked,
			single: true
		});
		await userEvent.setup().click(screen.getByText('Auto'));
		expect(onchange.mock.calls).toEqual([[['t2']]]);
		expect(onpicked).toHaveBeenCalledTimes(1);
	});

	it('tells nothing for the change of the topic chosen already', async () => {
		// A browser runs the microtasks of a click before its radio's change: the click told the
		// topic and the caller chose it before the change arrives.
		const onchange = vi.fn();
		render(TagPickerList, {
			title: 'Themen',
			scope: 'topic',
			tags,
			selected: ['t2'],
			onchange,
			single: true
		});
		await fireEvent.change(screen.getByRole('radio', { name: 'Auto' }));
		expect(onchange).not.toHaveBeenCalled();
	});
});
