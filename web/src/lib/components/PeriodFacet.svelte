<script lang="ts">
	import type { components } from '#lib/api/schema.ts';
	import {
		monthPeriod,
		periodOf,
		quickPick,
		RELATIVE_PERIODS,
		yearPeriod,
		type Filters
	} from '#lib/filters.ts';
	import { formatDate, formatNumber } from '#lib/i18n.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { phone } from '#lib/phone.svelte.ts';
	import Chip from '#lib/components/Chip.svelte';
	import { QUICK_PICKS } from '#lib/period-label.ts';

	type Period = Pick<Filters, 'dateFrom' | 'dateTo' | 'period'>;
	type Year = components['schemas']['YearCount'];

	// The period of the document date, compact however many years there are: quick picks, the
	// newest years as tiles (three to a row, year and count on one line, a bar for how many
	// documents each holds), the older ones behind one tile (a single one stays a tile); a chosen year (or the year of a chosen month) shows its
	// months as bars to choose from. A second tap lets a choice go. `showCounts`: not while
	// searching, the counts know no words. A quick pick moves with the day, a tile means its
	// year: "Letztes Jahr" and the tile of that year are two choices, though the same days today.
	let {
		years,
		undated,
		period,
		showCounts,
		onchange,
		shown = 9
	}: {
		years: readonly Year[];
		undated: number;
		period: Period;
		showCounts: boolean;
		onchange: (next: Period) => void;
		shown?: number;
	} = $props();

	const NONE: Period = { dateFrom: null, dateTo: null, period: null };
	const days = $derived(periodOf(period));
	// The days chosen as such; none while a quick pick stands.
	const chosen = $derived(period.period ? null : days);
	let older = $state(false);

	const today = new Date();
	const fixed = (days: Pick<Filters, 'dateFrom' | 'dateTo'>): Period => ({ ...days, period: null });

	const most = $derived(Math.max(1, ...years.map((year) => year.count)));
	const cut = $derived(years.length > shown + 1 ? shown : years.length);
	const newest = $derived(years.slice(0, cut));
	const rest = $derived(years.slice(cut));
	const tiles = $derived(older ? years : newest);
	// The year whose months show: the chosen one, that of the chosen month, or the year a quick
	// pick covers.
	const focus = $derived(
		days?.kind === 'year'
			? days.year
			: days?.kind === 'month'
				? Number(days.month.slice(0, 4))
				: null
	);
	const months = $derived.by(() => {
		if (focus === null) return [];
		const counts = new Map(
			(years.find((year) => year.year === focus)?.months ?? []).map((entry) => [
				entry.month,
				entry.count
			])
		);
		return Array.from({ length: 12 }, (_, index) => {
			const month = `${focus}-${String(index + 1).padStart(2, '0')}`;
			const date = new Date(focus, index, 1);
			return {
				month,
				count: counts.get(month) ?? 0,
				letter: formatDate(date, { month: 'narrow' }),
				name: formatDate(date, { month: 'long', year: 'numeric' })
			};
		});
	});
	const monthMost = $derived(Math.max(1, ...months.map((month) => month.count)));
</script>

<div class="flex flex-col gap-2.5">
	<div class="flex flex-wrap gap-1.5">
		{#each RELATIVE_PERIODS as quick (quick)}
			{@const active = period.period === quick}
			<Chip
				size={phone.current ? 'md' : 'sm'}
				pressed={active}
				onclick={() => onchange(active ? NONE : quickPick(quick, today))}
			>
				{QUICK_PICKS[quick]()}
			</Chip>
		{/each}
	</div>
	{#if years.length > 0}
		<div class="grid grid-cols-3 gap-1.5">
			{#each tiles as year (year.year)}
				{@const active = chosen?.kind === 'year' && chosen.year === year.year}
				<button
					type="button"
					aria-pressed={active}
					class={[
						'relative flex h-9 items-center justify-between gap-1 overflow-hidden rounded-lg border px-2 text-left transition-colors max-sm:h-11',
						active
							? 'border-primary/30 bg-panel font-medium text-brand'
							: 'bg-card hover:bg-secondary'
					]}
					onclick={() => onchange(active ? NONE : fixed(yearPeriod(year.year)))}
				>
					{#if showCounts}
						<span
							aria-hidden="true"
							class={['absolute bottom-0 left-0 h-1', active ? 'bg-primary/60' : 'bg-primary/30']}
							style:width={`${Math.round((year.count / most) * 100)}%`}
						></span>
					{/if}
					<span class="relative text-sm tabular-nums">{year.year}</span>
					{#if showCounts}
						<span
							class={[
								'relative text-xs tabular-nums',
								active ? 'text-brand/80' : 'text-muted-foreground'
							]}
						>
							{formatNumber(year.count)}
						</span>
					{/if}
				</button>
			{/each}
		</div>
		{#if rest.length > 0}
			<button
				type="button"
				aria-expanded={older}
				class="flex h-8 items-center justify-between rounded-lg border border-dashed px-2.5 text-xs text-muted-foreground hover:bg-secondary max-sm:h-11"
				onclick={() => (older = !older)}
			>
				<span>
					{m.facet_older({ from: String(rest[rest.length - 1].year), to: String(rest[0].year) })}
				</span>
				{#if showCounts}
					<span class="tabular-nums">
						{formatNumber(rest.reduce((sum, year) => sum + year.count, 0))}
					</span>
				{/if}
			</button>
		{/if}
		{#if months.length > 0}
			<div
				class="grid h-14 grid-cols-12 items-end gap-0.5 border-t pt-2"
				role="group"
				aria-label={m.facet_months({ year: String(focus) })}
			>
				{#each months as month (month.month)}
					{@const active = chosen?.kind === 'month' && chosen.month === month.month}
					<button
						type="button"
						aria-pressed={active}
						aria-label={m.facet_month_count({
							month: month.name,
							count: formatNumber(month.count)
						})}
						title={m.facet_month_count({ month: month.name, count: formatNumber(month.count) })}
						data-small-target
						disabled={month.count === 0 && !active}
						class="flex h-full flex-col items-center justify-end gap-0.5 text-nano text-muted-foreground disabled:opacity-40"
						onclick={() =>
							onchange(fixed(active ? yearPeriod(focus ?? 0) : monthPeriod(month.month)))}
					>
						<span
							aria-hidden="true"
							class={[
								'min-h-0.5 w-full max-w-2.5 rounded-sm',
								active ? 'bg-brand' : month.count > 0 ? 'bg-primary/70' : 'bg-border'
							]}
							style:height={`${Math.round((month.count / monthMost) * 32)}px`}
						></span>
						<span class={active ? 'font-semibold text-brand' : ''}>{month.letter}</span>
					</button>
				{/each}
			</div>
		{/if}
	{/if}
	{#if showCounts && undated > 0}
		<p class="text-xs text-muted-foreground">
			{m.facet_undated({ count: formatNumber(undated) })}
		</p>
	{/if}
</div>
