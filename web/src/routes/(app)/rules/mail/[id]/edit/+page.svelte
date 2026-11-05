<script lang="ts">
	import { page } from '$app/state';
	import MailRulePage from '#lib/components/rules/MailRulePage.svelte';
</script>

{#key page.params.id}
	<MailRulePage id={page.params.id ?? null} />
{/key}
