<script lang="ts" generics="T">
	import type { Snippet } from 'svelte';
	import { ChoiceBox } from '#lib/components/ui/choice/index.ts';
	import { cn } from '#lib/utils.ts';

	// One answer of a choice among a few, as a card (web/DESIGN.md, "Checkboxes, radios,
	// switches"): the radio at the start, what the answer is and does beside it. Chosen, the card
	// takes `border-primary` and `bg-panel`, a border, no ring. With `group` it takes part in a
	// group bound by value; alone `checked` and `onchange` say and change it. The card is the label:
	// a click anywhere chooses it.
	let {
		name,
		value,
		group = $bindable(),
		checked,
		onchange,
		disabled = false,
		class: className,
		children
	}: {
		name: string;
		value?: T;
		group?: T;
		checked?: boolean;
		onchange?: () => void;
		disabled?: boolean;
		class?: string;
		children: Snippet;
	} = $props();
</script>

<label
	class={cn(
		'flex items-start gap-3 rounded-xl border bg-card p-3 transition-colors has-[>input:checked]:border-primary has-[>input:checked]:bg-panel has-[>input:checked]:hover:bg-panel',
		disabled ? 'cursor-not-allowed opacity-70' : 'cursor-pointer hover:bg-secondary/60',
		className
	)}
>
	<ChoiceBox
		type="radio"
		{name}
		{value}
		bind:group
		{checked}
		{disabled}
		{onchange}
		class="mt-0.5"
	/>
	<span class="flex min-w-0 flex-1 flex-col gap-0.5">{@render children()}</span>
</label>
