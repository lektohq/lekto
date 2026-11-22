<script lang="ts">
	import { Badge } from '#lib/components/ui/badge/index.ts';
	import { masterDataDialogs } from '#lib/masterdata-dialog.svelte.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { session } from '#lib/session.svelte.ts';

	// The rule of a document type's title pattern: a badge; for admins it opens the type's
	// dialog right here (it knows it came from the rule). It stands above the row's link. The
	// one badge that is a button (web/DESIGN.md, "Badges"): its line is 16 px tall, its hit area
	// 40 px with a mouse and a finger's 44 px on a phone.
	let { documentTypeId, name, ruleId }: { documentTypeId: string; name: string; ruleId: string } =
		$props();
</script>

<Badge variant="note">
	{#if session.isAdmin}
		<button
			type="button"
			class="relative z-10 cursor-pointer after:absolute after:-inset-x-2 after:-inset-y-3 hover:underline max-sm:after:-inset-y-3.5"
			onclick={() => masterDataDialogs.open('document-types', documentTypeId, { fromRule: ruleId })}
			>{m.rule_title_pattern_of({ type: name })}</button
		>
	{:else}
		{m.rule_title_pattern_of({ type: name })}
	{/if}
</Badge>
