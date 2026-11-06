<script lang="ts">
	import { cautions, summaryOf, type Mailbox } from '#lib/mailboxes.ts';
	import { reasonText } from '#lib/reasons.ts';

	// What a mailbox says under its name, in its row of the intake channels and in the head of
	// its page alike: server · folders · interval · the last fetch, why a fetch failed
	// (`destructive`), and what wants a look (`lane-yellow-foreground`: a mail left out, a step
	// the server refused).
	let { mailbox }: { mailbox: Mailbox } = $props();
</script>

<span class="text-sm text-muted-foreground">{summaryOf(mailbox)}</span>
{#if mailbox.status.error}
	<span class="text-sm text-destructive">{reasonText(mailbox.status.error)}</span>
{/if}
{#each cautions(mailbox) as caution (caution.key)}
	<span class="text-sm text-lane-yellow-foreground">{caution.text}</span>
{/each}
