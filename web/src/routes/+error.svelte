<script lang="ts">
	import { online } from 'svelte/reactivity/window';
	import { page } from '$app/state';
	import Logo from '#lib/components/Logo.svelte';
	import Mascot from '#lib/components/Mascot.svelte';
	import { Button } from '#lib/components/ui/button/index.ts';
	import { home } from '#lib/navigation.ts';
	import { m } from '#lib/paraglide/messages.js';
	import PageTitle from '#lib/components/page/PageTitle.svelte';

	const notFound = $derived(page.status === 404);
	// No answer and no connection (web/DESIGN.md, "App"): it says so and loads again by itself
	// once the device is back online.
	const offline = $derived(page.error?.offline === true && online.current === false);
	let wasOffline = false;
	$effect(() => {
		if (offline) wasOffline = true;
		else if (wasOffline && page.error?.offline) location.reload();
	});
	const title = $derived(
		offline ? m.offline_title() : notFound ? m.error_not_found() : m.error_title()
	);
</script>

<svelte:head><title>{title}</title></svelte:head>

<main class="mx-auto flex min-h-screen max-w-xl flex-col justify-center gap-6 px-6">
	<!-- A page that does not exist gets the owl in place of the logo; a real error keeps the
	     logo, the owl would be too playful there (web/DESIGN.md, "Logo and owl"). -->
	{#if notFound}
		<Mascot class="w-20" />
	{:else}
		<Logo class="text-xl" />
	{/if}
	<PageTitle>{title}</PageTitle>
	{#if offline}
		<p class="text-muted-foreground">{m.offline_hint()}</p>
	{:else if !notFound && page.error?.message}
		<p class="text-muted-foreground">{page.error.message}</p>
	{/if}
	<div class="flex gap-3">
		<Button href={home()}>{m.error_home()}</Button>
		{#if !notFound}
			<Button variant="secondary" onclick={() => location.reload()}>{m.error_retry()}</Button>
		{/if}
	</div>
</main>
