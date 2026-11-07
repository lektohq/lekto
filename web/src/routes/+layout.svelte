<script lang="ts">
	import '../app.css';
	import { ModeWatcher, mode } from 'mode-watcher';
	import { onMount } from 'svelte';
	import { startAppUpdates } from '#lib/app-update.ts';
	import { Toaster } from '#lib/components/ui/sonner/index.ts';
	import { getLocale } from '#lib/i18n.ts';
	import { setThemeColor } from '#lib/theme-color.ts';

	let { children } = $props();

	$effect(() => {
		document.documentElement.lang = getLocale();
	});

	$effect(() => {
		setThemeColor(mode.current === 'dark');
	});

	onMount(startAppUpdates);
</script>

<!-- No transition-blocking <style> element: the CSP allows no inline style elements. -->
<ModeWatcher disableHeadScriptInjection disableTransitions={false} />
<Toaster richColors={false} closeButton />
{@render children()}
