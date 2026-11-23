<script lang="ts">
	import ExternalLink from '@lucide/svelte/icons/external-link';
	import { api } from '#lib/api/client.ts';
	import { unwrap } from '#lib/api/call.ts';
	import type { components } from '#lib/api/schema.ts';
	import * as Alert from '#lib/components/ui/alert/index.ts';
	import { Button } from '#lib/components/ui/button/index.ts';
	import { formatDate, formatMoment } from '#lib/i18n.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { session } from '#lib/session.svelte.ts';

	// A newer Lekto is out (`GET /version`; .knowledge/open/update-notifier-fas.md): a note above
	// the tabs of the page System, for admins only, while the release is newer than the running
	// one (Tobi, 19.11.2026, after a mock). It goes by itself once the new version runs; a
	// failed load shows nothing, as without news.
	let version = $state<components['schemas']['VersionOut'] | null>(null);

	$effect(() => {
		if (!session.isAdmin) return;
		unwrap(api.GET('/api/v1/version'))
			.then((found) => (version = found))
			.catch(() => (version = null));
	});

	const latest = $derived(version?.update_available ? version.latest : null);
</script>

{#if latest && version}
	<Alert.Root variant="note" role="status" class="flex flex-wrap items-center gap-x-4 gap-y-2">
		<div class="min-w-0 flex-1">
			<Alert.Title>{m.update_title({ version: latest.version })}</Alert.Title>
			<Alert.Description>
				{m.update_meta({
					running: version.lekto_version,
					published: formatDate(latest.published_at),
					checked: version.checked_at ? formatMoment(version.checked_at) : ''
				})}
			</Alert.Description>
		</div>
		<Button variant="outline" size="sm" href={latest.url} target="_blank" rel="noopener noreferrer">
			<ExternalLink aria-hidden="true" />
			{m.update_release_notes()}
		</Button>
	</Alert.Root>
{/if}
