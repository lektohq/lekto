// The stat tile: a figure with its word below, a card of size `sm` in every tab of the system
// page (web/DESIGN.md, "Cards").
import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import StatTile from './StatTile.svelte';

const tile = () => document.querySelector<HTMLElement>('[data-slot="card"]');

describe('the stat tile', () => {
	it('is a small card with the figure and its word', () => {
		render(StatTile, { value: '12345', label: 'Documents' });
		expect(tile()?.dataset.size).toBe('sm');
		expect(tile()?.className).toContain('rounded-2xl');
		expect(tile()?.className).toContain('bg-card');
		expect(screen.getByText('12345').className).toContain('text-figure');
		expect(screen.getByText('Documents').className).toContain('text-muted-foreground');
	});

	it('takes the ground, the text and the edge of a lane from the tones', () => {
		render(StatTile, { value: '3', label: 'Failed', tone: 'red' });
		const classes = tile()?.className ?? '';
		expect(classes).toContain('bg-lane-red');
		expect(classes).toContain('text-lane-red-foreground');
		expect(classes).toContain('border-lane-red-foreground/30');
		// An edge, no ring; the word takes the tone's text colour.
		expect(classes).not.toContain('ring');
		expect(screen.getByText('Failed').className).not.toContain('text-muted-foreground');
	});

	it('stands on the surface when quiet, and shows a hint below a stronger word', () => {
		render(StatTile, { value: '7', label: 'Done', hint: 'Kept for a week', tone: 'quiet' });
		expect(tile()?.className).toContain('bg-surface');
		expect(screen.getByText('Done').className).toContain('font-medium');
		expect(screen.getByText('Kept for a week').className).toContain('text-muted-foreground');
	});

	it('writes a technical name in code and a value with its unit smaller', () => {
		render(StatTile, { value: 'model-12345', label: 'Model', kind: 'code' });
		expect(screen.getByText('model-12345').className).toContain('font-mono');
		render(StatTile, { value: '12 MB', label: 'Size', kind: 'value' });
		expect(screen.getByText('12 MB').className).toContain('text-lg');
	});
});
