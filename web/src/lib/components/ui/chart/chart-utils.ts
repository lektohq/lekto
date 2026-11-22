import type { Component } from 'svelte';

// Colors are tokens that follow the theme (`var(--chart-1)`): no theme of their own, which
// needed the inserted `<style>` element the CSP forbids.
export type ChartConfig = {
	[k in string]: {
		label?: string;
		icon?: Component;
		color?: string;
	};
};
