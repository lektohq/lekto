<script lang="ts">
	import { mode } from 'mode-watcher';
	import { Toaster as Sonner, type ToasterProps as SonnerProps } from 'svelte-sonner';
	import Loader2Icon from '@lucide/svelte/icons/loader-2';
	import CircleCheckIcon from '@lucide/svelte/icons/circle-check';
	import OctagonXIcon from '@lucide/svelte/icons/octagon-x';
	import InfoIcon from '@lucide/svelte/icons/info';
	import TriangleAlertIcon from '@lucide/svelte/icons/triangle-exclamation-point';
	import { m } from '#lib/paraglide/messages.js';
	import { TOAST_CLASS, TOAST_CLOSE_CLASS } from '#lib/toasts.ts';

	let { ...restProps }: SonnerProps = $props();
</script>

<!-- The names of the region and of a toast's ✕ come from the messages: the library's are English. -->
<Sonner
	containerAriaLabel={m.toast_region()}
	closeButtonAriaLabel={m.toast_close()}
	theme={mode.current}
	class="group"
	style="--normal-bg: var(--color-popover); --normal-text: var(--color-popover-foreground); --normal-border: var(--color-border);"
	toastOptions={{
		classes: {
			toast: TOAST_CLASS,
			closeButton: TOAST_CLOSE_CLASS
		}
	}}
	{...restProps}
>
	{#snippet loadingIcon()}
		<Loader2Icon class="size-4 motion-safe:animate-spin" />
	{/snippet}
	{#snippet successIcon()}
		<CircleCheckIcon class="size-4" />
	{/snippet}
	{#snippet errorIcon()}
		<OctagonXIcon class="size-4" />
	{/snippet}
	{#snippet infoIcon()}
		<InfoIcon class="size-4" />
	{/snippet}
	{#snippet warningIcon()}
		<TriangleAlertIcon class="size-4" />
	{/snippet}
</Sonner>
