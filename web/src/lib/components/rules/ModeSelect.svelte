<script lang="ts">
	import Select from '#lib/components/Select.svelte';
	import { m } from '#lib/paraglide/messages.js';
	import { cn } from '#lib/utils.ts';

	// How a rule's conditions go together, the same words for document and mail rules: all of
	// them, or at least one.
	let {
		value,
		onchange,
		class: className = ''
	}: {
		value: 'all' | 'any';
		onchange: (mode: 'all' | 'any') => void;
		class?: string;
	} = $props();

	const modes = [
		{ value: 'all', label: m.rule_mode_all() },
		{ value: 'any', label: m.rule_mode_any() }
	];
</script>

<Select
	aria-label={m.rule_mode()}
	{value}
	options={modes}
	onchange={(mode) => onchange(mode === 'any' ? 'any' : 'all')}
	class={cn('w-full sm:w-56', className)}
/>
