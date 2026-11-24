<script lang="ts">
	import { setAppBadge } from '#lib/app-badge.ts';
	import { retryDelay } from '#lib/backoff.ts';
	import AppShell from '#lib/components/AppShell.svelte';
	import OnDemand from '#lib/components/OnDemand.svelte';
	import { masterDataDialogs } from '#lib/masterdata-dialog.svelte.ts';
	import { events } from '#lib/events.svelte.ts';
	import { inbox } from '#lib/inbox.svelte.ts';
	import { closeWaiting, endForeignSubscription } from '#lib/push-device.ts';
	import { recheckSession, session } from '#lib/session.svelte.ts';
	import { uploads } from '#lib/upload.svelte.ts';
	import { whileVisible } from '#lib/visible.ts';

	let { children } = $props();

	// The effects below follow the signed-in user, not the user object: asking the server anew
	// who is signed in (`recheckSession`) must not restart the stream or drop the uploads.
	const userId = $derived(session.user?.id ?? null);

	// The installed app's icon shows the caller's own inbox, as a notification sets it, also
	// while the counter counts everyone's (web/DESIGN.md, "App"). Nothing waits any more: the
	// notification that said so goes, since no message can take it back while the app is closed.
	$effect(() => {
		if (!userId) return;
		setAppBadge(inbox.own);
		if (inbox.own === 0) void closeWaiting();
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
		// At the start `inbox.start()` reads the counter itself.
		if (!userId || !reconnected) return;
		void recheckSession();
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
	// A tab that is hidden for a while lets go of it and opens it again when it is shown, as a
	// reconnect (the pages read anew): over HTTP/1.1 a browser opens at most six connections to
	// a host, and six tabs each holding one left none for any request (`lib/visible.ts`).
	$effect(() => {
		if (!userId) return;
		let retry: ReturnType<typeof setTimeout> | undefined;
		let ended = false;
		let paused = false;
		failures = 0;
		const open = () => {
			paused = false;
			events.start(async () => {
				if (ended) return;
				// Without a session it leads to the sign-in page, as another user it starts
				// afresh; while the API is not reachable the user stays and the stream tries again.
				await recheckSession();
				if (!ended && !paused && session.user) retry = setTimeout(open, retryDelay(++failures));
			});
		};
		const unwatch = whileVisible(open, () => {
			paused = true;
			clearTimeout(retry);
			events.pause();
		});
		inbox.start();
		return () => {
			ended = true;
			unwatch();
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
<!-- The dialogs of the master data open from any page, but most never open one (`OnDemand`). -->
{#if userId}
	<OnDemand
		load={() => import('#lib/components/MasterDataDialogHost.svelte')}
		wanted={masterDataDialogs.request !== null || masterDataDialogs.nested.length > 0}
	/>
{/if}
