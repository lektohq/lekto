<script lang="ts" module>
	export interface Option {
		value: string;
		label: string;
	}
</script>

<script lang="ts">
	import Check from '@lucide/svelte/icons/check';
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
	import { Select as SelectPrimitive } from 'bits-ui';
	import { tick } from 'svelte';
	import { phone } from '#lib/phone.svelte.ts';
	import { cn } from '#lib/utils.ts';
	import { FIELD as FIELD_LOOK, FIELD_HEIGHT } from '#lib/components/ui/field-look.ts';

	// A choice from a short, fixed list, styled like the inputs. On a phone the system's own
	// picker (the most comfortable with a thumb, Tobi 20.10.2026); wider, a list in the look of
	// the other pickers, by keyboard too (arrows, typing the first letters, Enter).
	//
	// The field shows `value`, never a choice of its own: a caller that saves a choice at once
	// (`bind:value` with a getter and a setter) may refuse it, and the field then stands at
	// what is stored, ready for the same choice again.
	let {
		value = $bindable(''),
		options,
		id,
		class: className = '',
		disabled = false,
		'aria-label': ariaLabel,
		'aria-invalid': ariaInvalid,
		onchange
	}: {
		value?: string;
		options: readonly Option[];
		id?: string;
		class?: string;
		disabled?: boolean;
		'aria-label'?: string;
		'aria-invalid'?: boolean;
		/** Called with the new value when the user picks one. */
		onchange?: (value: string) => void;
	} = $props();

	const FIELD = cn(FIELD_LOOK, FIELD_HEIGHT);
	let system = $state<HTMLSelectElement | null>(null);

	function picked(next: string) {
		value = next;
		onchange?.(next);
		// The system's select keeps what was picked; where the caller did not take it, back.
		void tick().then(() => {
			if (system && system.value !== value) system.value = value;
		});
	}
	const shown = $derived(options.find((option) => option.value === value)?.label ?? '');
</script>

{#if phone.current}
	<select
		{id}
		bind:this={system}
		bind:value={() => value, picked}
		{disabled}
		aria-label={ariaLabel}
		aria-invalid={ariaInvalid}
		class={cn(FIELD, className, 'max-sm:h-11')}
	>
		{#each options as option (option.value)}
			<option value={option.value}>{option.label}</option>
		{/each}
	</select>
{:else}
	<SelectPrimitive.Root
		type="single"
		bind:value={() => value, picked}
		{disabled}
		items={[...options]}
	>
		<!-- A combobox as the native select is one: named by its label, its value read out. -->
		<SelectPrimitive.Trigger
			{id}
			role="combobox"
			data-value={value}
			aria-label={ariaLabel}
			aria-invalid={ariaInvalid}
			class={cn(FIELD, 'flex items-center gap-2 text-left', className)}
		>
			<span class="min-w-0 flex-1 truncate">{shown}</span>
			<ChevronDown class="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
		</SelectPrimitive.Trigger>
		<SelectPrimitive.Portal>
			<SelectPrimitive.Content
				sideOffset={4}
				class="z-50 max-h-(--bits-select-content-available-height) min-w-(--bits-select-anchor-width) overflow-y-auto rounded-lg bg-popover p-1 text-popover-foreground shadow-md ring-1 ring-foreground/10 outline-hidden data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:animate-in data-[state=open]:fade-in-0"
			>
				<SelectPrimitive.Viewport>
					{#each options as option (option.value)}
						<SelectPrimitive.Item
							value={option.value}
							label={option.label}
							class="relative flex cursor-default items-center gap-2 rounded-sm py-1.5 pr-8 pl-2 text-sm outline-hidden select-none data-[disabled]:pointer-events-none data-[disabled]:opacity-50 data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground"
						>
							{#snippet children({ selected })}
								<span class="min-w-0 flex-1 truncate">{option.label}</span>
								{#if selected}
									<Check class="absolute right-2 size-4" aria-hidden="true" />
								{/if}
							{/snippet}
						</SelectPrimitive.Item>
					{/each}
				</SelectPrimitive.Viewport>
			</SelectPrimitive.Content>
		</SelectPrimitive.Portal>
	</SelectPrimitive.Root>
{/if}
