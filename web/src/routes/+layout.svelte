<script lang="ts">
	import '../app.css';
	import { ModeWatcher, mode } from 'mode-watcher';
	import { onMount } from 'svelte';
	import { startAppUpdates } from '#lib/app-update.ts';
	import { Toaster } from '#lib/components/ui/sonner/index.ts';
	import { getLocale } from '#lib/i18n.ts';
	import { install } from '#lib/install.svelte.ts';
	import { setThemeColor } from '#lib/theme-color.ts';

	let { children } = $props();

	$effect(() => {
		document.documentElement.lang = getLocale();
	});

	$effect(() => {
		setThemeColor(mode.current === 'dark');
	});

	onMount(() => {
		install.watch();
		startAppUpdates();
	});
</script>

<!-- No transition-blocking <style> element: the CSP allows no inline style elements. -->
<ModeWatcher disableHeadScriptInjection disableTransitions={false} />
<!-- Above the home indicator of the installed app (web/DESIGN.md, "App"). -->
<Toaster
	richColors={false}
	closeButton
	mobileOffset={{
		top: 'calc(16px + env(safe-area-inset-top))',
		right: 'calc(16px + env(safe-area-inset-right))',
		bottom: 'calc(16px + env(safe-area-inset-bottom))',
		left: 'calc(16px + env(safe-area-inset-left))'
	}}
/>
{@render children()}
