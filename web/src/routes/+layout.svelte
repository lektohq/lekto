<script lang="ts">
	import '../app.css';
	import { ModeWatcher, mode } from 'mode-watcher';
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { answerOpen } from '#lib/app-open.ts';
	import { startAppUpdates } from '#lib/app-update.ts';
	import { Toaster } from '#lib/components/ui/sonner/index.ts';
	import { BASE } from '#lib/base.ts';
	import { getLocale } from '#lib/i18n.ts';
	// Heard from the start: the browser's offer to install may come before a page asks for it.
	import '#lib/install.svelte.ts';
	import { setThemeColor } from '#lib/theme-color.ts';

	let { children } = $props();

	$effect(() => {
		document.documentElement.lang = getLocale();
	});

	$effect(() => {
		setThemeColor(mode.current === 'dark');
	});

	onMount(() => {
		startAppUpdates();
		// A tap on a notification moves the open app through its router.
		return answerOpen(BASE, (path) => goto(path));
	});
</script>

<!-- No transition-blocking <style> element: the CSP allows no inline style elements. -->
<ModeWatcher disableHeadScriptInjection disableTransitions={false} />
<!-- Above the home indicator of the installed app and beside the notch (web/DESIGN.md,
     "App"): the library takes `mobileOffset` up to 600 px of width only, a phone held sideways
     is wider and takes `offset`. -->
<Toaster
	richColors={false}
	closeButton
	offset={{
		top: 'calc(24px + env(safe-area-inset-top))',
		right: 'calc(24px + env(safe-area-inset-right))',
		bottom: 'calc(24px + env(safe-area-inset-bottom))',
		left: 'calc(24px + env(safe-area-inset-left))'
	}}
	mobileOffset={{
		top: 'calc(16px + env(safe-area-inset-top))',
		right: 'calc(16px + env(safe-area-inset-right))',
		bottom: 'calc(16px + env(safe-area-inset-bottom))',
		left: 'calc(16px + env(safe-area-inset-left))'
	}}
/>
{@render children()}
