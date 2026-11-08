<script lang="ts">
	// `DateInput` in component tests: jsdom has no layout for the date picker's segments, so a
	// plain date input stands in (with a time for `granularity` `minute`), with the same props
	// (`tests/setup.ts`).
	let {
		value = $bindable(''),
		id,
		label,
		min,
		max,
		granularity = 'day',
		disabled = false,
		invalid = false,
		class: className,
		onchange
	}: {
		value?: string;
		id?: string;
		label: string;
		min?: string;
		max?: string;
		granularity?: 'day' | 'minute';
		disabled?: boolean;
		invalid?: boolean;
		class?: string;
		onchange?: (value: string) => void;
	} = $props();
</script>

<input
	data-stand="DateInput"
	{id}
	class={className}
	type={granularity === 'minute' ? 'datetime-local' : 'date'}
	aria-label={label}
	aria-invalid={invalid || undefined}
	{min}
	{max}
	{disabled}
	bind:value
	oninput={(event) => onchange?.(event.currentTarget.value)}
/>
