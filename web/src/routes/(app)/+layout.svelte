<script lang="ts">
	import { setAppBadge } from '#lib/app-badge.ts';
	import { retryDelay } from '#lib/backoff.ts';
	import AppShell from '#lib/components/AppShell.svelte';
	import MasterDataDialogHost from '#lib/components/MasterDataDialogHost.svelte';
	import { events } from '#lib/events.svelte.ts';
	import { inbox } from '#lib/inbox.svelte.ts';
	import { endForeignSubscription } from '#lib/push-device.ts';
	import { recheckSession, session } from '#lib/session.svelte.ts';
	import { uploads } from '#lib/upload.svelte.ts';

	let { children } = $props();

	// The effects below follow the signed-in user, not the user object: asking the server anew
	// who is signed in (`recheckSession`) must not restart the stream or drop the uploads.
	const userId = $derived(session.user?.id ?? null);

	// The installed app's icon shows what the inbox counter shows (web/DESIGN.md, "App").
	$effect(() => {
		if (userId) setAppBadge(inbox.summary?.open);
	});

	// A push subscription this browser still has from someone else (their session ran out, they
	// never signed out) ends when another user starts the app.
	$effect(() => {
		if (userId) void endForeignSubscription();
	});

	// After a reconnect the counter may be stale, and so may the user: the API closes the stream
	// of a session that ended, and the browser reconnects as whoever holds the cookie now.
	$effect(() => {
		const reconnected = events.generation > 0;
		if (!userId) return;
		if (reconnected) void recheckSession();
		void inbox.refresh();
	});

	// Back in front: in another tab someone else may have signed in meanwhile.
	$effect(() => {
		if (!userId) return;
		const seen = () => {
			if (document.visibilityState === 'visible') void recheckSession();
		};
		document.addEventListener('visibilitychange', seen);
		return () => document.removeEventListener('visibilitychange', seen);
	});

	// Attempts in a row that the API closed; the wait before the next one grows with them.
	let failures = 0;
	$effect(() => {
		if (events.connected) failures = 0;
	});

	// One event stream while someone is signed in; it closes with the session (sign-out, 401).
	$effect(() => {
		if (!userId) return;
		let retry: ReturnType<typeof setTimeout> | undefined;
		let ended = false;
		failures = 0;
		const open = () =>
			events.start(async () => {
				if (ended) return;
				// Without a session it leads to the sign-in page, as another user it starts
				// afresh; while the API is not reachable the user stays and the stream tries again.
				await recheckSession();
				if (!ended && session.user) retry = setTimeout(open, retryDelay(++failures));
			});
		open();
		inbox.start();
		return () => {
			ended = true;
			clearTimeout(retry);
			inbox.stop();
			events.stop();
			uploads.reset();
		};
	});
</script>

<AppShell>
	{@render children()}
</AppShell>
{#if userId}<MasterDataDialogHost />{/if}
