<script lang="ts">
	import { api } from '#lib/api/client.ts';
	import { unwrap } from '#lib/api/call.ts';
	import { openBeam } from '#lib/beam.svelte.ts';
	import BeamTitle from '#lib/components/BeamTitle.svelte';
	import { formatNumber, listLocale, quoted } from '#lib/i18n.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { partNumber, type Separation } from '#lib/separation.ts';

	// The rows of the separation step (web/DESIGN.md, "Fassung"; Tobi, 11.11.2026): the codes it
	// looked for, the sheets and the other codes it found; for a part of a stack or pages a person
	// split off, the document they came from by its title now (the title of then where it is gone
	// or out of reach); or why it did not look.
	let { separation }: { separation: Separation } = $props();

	const from = $derived(
		separation.kind === 'part' || separation.kind === 'split' ? separation.from : null
	);
	let origin = $state<{ id: string; title: string } | null>(null);
	$effect(() => {
		const id = from;
		origin = null;
		if (!id) return;
		let stale = false;
		void (async () => {
			try {
				const found = await unwrap(api.GET('/api/v1/documents/{id}', { params: { path: { id } } }));
				if (!stale) origin = { id, title: found.title };
			} catch {
				// Gone or out of reach: the title of then stands.
			}
		})();
		return () => {
			stale = true;
		};
	});

	const and = (items: string[]) =>
		new Intl.ListFormat(listLocale(), { type: 'conjunction' }).format(items);

	/** The sheets found, each with the format of its code. */
	function sheetsFound(found: Extract<Separation, { kind: 'looked' }>): string {
		return and(
			found.sheets.map((page) => {
				const formats = found.codes
					.filter((code) => code.separator && code.page === page)
					.map((code) => code.format);
				return formats.length > 0
					? m.details_separate_sheet({ page: String(page), format: formats.join(', ') })
					: m.details_page_short({ page: String(page) });
			})
		);
	}

	const versionHow: Record<string, (args: { version: string }) => string> = {
		edited: m.details_separate_version_edited,
		replaced: m.details_separate_version_replaced,
		merged: m.details_separate_version_merged
	};

	function why(found: Separation): string {
		if (found.kind === 'off') return m.details_separate_why_off();
		if (found.kind === 'mail') return m.details_separate_why_mail();
		if (found.kind === 'migration') return m.details_separate_why_migration();
		if (found.kind === 'too_long')
			return m.details_separate_why_too_long({
				pages: formatNumber(found.pages),
				max: formatNumber(found.max)
			});
		if (found.kind !== 'new_version') return '';
		const how = found.how && found.version !== null ? versionHow[found.how] : undefined;
		return [m.details_separate_why_new_version(), how?.({ version: String(found.version) })]
			.filter(Boolean)
			.join(' ');
	}
</script>

{#snippet originTitle(title: string)}
	{#if origin}
		{@const shown = origin}
		<BeamTitle
			title={shown.title}
			onview={() => openBeam([shown.id], shown.id, m.tab_processing())}
		/>
	{:else}
		<span>{quoted(title)}</span>
	{/if}
{/snippet}

{#if separation.kind === 'looked'}
	{@const others = separation.codes.filter((code) => !code.separator)}
	{#if separation.separators.length > 0}
		<dt class="text-muted-foreground">{m.details_separate_sought()}</dt>
		<dd class="flex min-w-0 flex-wrap items-baseline gap-x-1.5">
			{#each separation.separators as code (code)}
				<span class="font-mono text-meta">{code}</span>
			{/each}
			<span>
				{separation.pages === 1
					? m.details_separate_on_page()
					: m.details_separate_on_pages({ count: formatNumber(separation.pages) })}
			</span>
		</dd>
	{/if}
	<dt class="text-muted-foreground">{m.details_separate_found()}</dt>
	<dd>{separation.sheets.length > 0 ? sheetsFound(separation) : m.summary_no_separator()}</dd>
	{#if others.length > 0}
		<dt class="text-muted-foreground">{m.details_separate_other()}</dt>
		<dd>
			{and(
				others.map((code) =>
					m.details_separate_other_code({ format: code.format, page: String(code.page) })
				)
			)}
		</dd>
	{/if}
{:else if separation.kind === 'part'}
	{@const number = partNumber(separation.pages, separation.sheets, separation.stackPages)}
	<dt class="text-muted-foreground">{m.details_separate_origin()}</dt>
	<dd class="flex min-w-0 flex-wrap items-center gap-x-1.5">
		<span>
			{number
				? m.details_separate_part_of({
						part: formatNumber(number.part),
						parts: formatNumber(number.parts)
					})
				: m.summary_not_looked_part()}
		</span>
		{@render originTitle(separation.title)}
	</dd>
	<dt class="text-muted-foreground">{m.details_separate_sought()}</dt>
	<dd>{m.details_separate_not_again()}</dd>
{:else if separation.kind === 'split'}
	<dt class="text-muted-foreground">{m.details_separate_origin()}</dt>
	<dd class="flex min-w-0 flex-wrap items-center gap-x-1.5">
		<span>{m.details_separate_split_from()}</span>
		{@render originTitle(separation.title)}
	</dd>
	<dt class="text-muted-foreground">{m.details_separate_sought()}</dt>
	<dd>{m.details_separate_not_split()}</dd>
{:else}
	<dt class="text-muted-foreground">{m.details_separate_why()}</dt>
	<dd>{why(separation)}</dd>
{/if}
