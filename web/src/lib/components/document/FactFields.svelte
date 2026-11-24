<script lang="ts">
	import Select from '#lib/components/Select.svelte';
	import { Input } from '#lib/components/ui/input/index.ts';
	import { FACT_ROLES, roleLabel, type FactRole } from '#lib/facts.ts';
	import { m } from '#lib/paraglide/messages.js';

	// The value of a fact as the document writes it and its role: the fields a person adds a
	// fact with (`FactAdd`) and corrects one with (`FactDecide`).
	let { value = $bindable(), role = $bindable() }: { value: string; role: FactRole } = $props();
</script>

<label class="flex flex-col gap-1 text-sm">
	<span class="text-xs text-muted-foreground">{m.facts_decide_value()}</span>
	<Input class="font-mono" bind:value autocomplete="off" spellcheck="false" />
</label>
<label class="flex flex-col gap-1 text-sm">
	<span class="text-xs text-muted-foreground">{m.facts_decide_role()}</span>
	<Select
		bind:value={role}
		aria-label={m.facts_decide_role()}
		options={FACT_ROLES.map((item) => ({ value: item, label: roleLabel(item) }))}
	/>
</label>
