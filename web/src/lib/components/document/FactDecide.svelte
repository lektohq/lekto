<script lang="ts">
	import { untrack } from 'svelte';
	import ConfirmDialog from '#lib/components/ConfirmDialog.svelte';
	import FactFields from '#lib/components/document/FactFields.svelte';
	import { Button } from '#lib/components/ui/button/index.ts';
	import * as Card from '#lib/components/ui/card/index.ts';
	import { onlyByPerson, type FactDecision, type FactRole, type KeptFact } from '#lib/facts.ts';
	import { kindLabel } from '#lib/identifiers.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { Choice } from '#lib/components/ui/choice/index.ts';

	// A person's decision about one fact of the document: its value and role corrected (for
	// admins at the document's contact too), rejected, or a decision withdrawn. A rejected fact
	// is only restored.
	let {
		fact,
		contact = null,
		busy = false,
		ondecide,
		oncancel
	}: {
		fact: KeptFact;
		/** The document's contact an admin may correct the value at too; null: not offered. */
		contact?: string | null;
		busy?: boolean;
		ondecide: (decision: FactDecision) => void;
		oncancel: () => void;
	} = $props();

	// What the form starts from: the fact as it was opened.
	const shownValue = (of: KeptFact) => of.written ?? of.value;
	let value = $state('');
	let role = $state<FactRole>('contact');
	let atContact = $state(false);
	// Anew for another fact only: the facts reload with every event of the document, and what
	// the person typed stays.
	const key = $derived(`${fact.kind}:${fact.value}`);
	$effect.pre(() => {
		void key;
		untrack(() => {
			value = shownValue(fact);
			role = fact.role;
			atContact = false;
		});
	});

	const rejected = $derived(fact.state === 'rejected');
	const decided = $derived(fact.state !== undefined && fact.state !== 'found');
	const changedValue = $derived(value.trim() !== '' && value.trim() !== shownValue(fact));
	const changed = $derived(changedValue || role !== fact.role);
	const base = $derived({ kind: fact.kind, value: fact.value });

	// A fact only a person added is gone once withdrawn: asked first.
	let removing = $state(false);
	const withdraw = () => ondecide({ ...base, action: 'withdraw' });

	function correct() {
		if (!changed) return;
		ondecide({
			...base,
			action: 'correct',
			...(role !== fact.role ? { role } : {}),
			...(changedValue ? { new_value: value.trim() } : {}),
			...(changedValue && atContact ? { at_contact: true } : {})
		});
	}
</script>

<Card.Root
	as="form"
	size="sm"
	class="mx-2.5 mb-2.5 flex flex-col gap-2.5"
	onsubmit={(event) => {
		event.preventDefault();
		correct();
	}}
>
	<span class="text-sm font-medium">{m.facts_decide_title({ kind: kindLabel(fact.kind) })}</span>
	{#if rejected}
		<span class="text-xs text-muted-foreground">{m.facts_decide_rejected_hint()}</span>
	{:else}
		<FactFields bind:value bind:role />
		{#if contact && changedValue}
			<Choice bind:checked={atContact}>
				<span>{m.facts_decide_at_contact({ contact })}</span>
			</Choice>
		{/if}
	{/if}
	<div class="flex flex-wrap justify-end gap-2">
		<Button type="button" variant="ghost" size="sm" onclick={oncancel}>{m.cancel()}</Button>
		{#if rejected}
			<Button type="button" size="sm" {busy} onclick={withdraw}>
				{m.facts_decide_restore()}
			</Button>
		{:else}
			{#if decided}
				<Button
					type="button"
					variant="outline"
					size="sm"
					{busy}
					onclick={() => (onlyByPerson(fact) ? (removing = true) : withdraw())}
				>
					{onlyByPerson(fact) ? m.facts_decide_remove() : m.facts_decide_undo()}
				</Button>
			{/if}
			{#if !onlyByPerson(fact)}
				<Button
					type="button"
					variant="outline"
					size="sm"
					{busy}
					onclick={() => ondecide({ ...base, action: 'reject' })}
				>
					{m.facts_decide_reject()}
				</Button>
			{/if}
			<Button type="submit" size="sm" {busy} disabled={!changed}>
				{m.facts_decide_save()}
			</Button>
		{/if}
	</div>
</Card.Root>

<ConfirmDialog
	bind:open={removing}
	title={m.facts_remove_title({ kind: kindLabel(fact.kind), value: shownValue(fact) })}
	description={m.facts_remove_confirm()}
	confirmLabel={m.facts_decide_remove()}
	onconfirm={async () => withdraw()}
/>
