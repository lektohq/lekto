<script lang="ts">
	import StepCard from '#lib/components/document/StepCard.svelte';
	import { m } from '#lib/paraglide/messages.js';
	import { isAtWork, type Node } from '#lib/pipeline.ts';
	import { stepLook, type StepsProps } from '#lib/step-look.ts';
	import { STEP_BORDER, STEP_TINT, TONE_DOT } from '#lib/tones.ts';
	import { PHASE_LABELS, type Step } from '#lib/steps.ts';
	import { cn } from '#lib/utils.ts';
	import SectionTitle from '#lib/components/page/SectionTitle.svelte';
	import Eyebrow from '#lib/components/page/Eyebrow.svelte';

	// The steps of a run on a narrower screen (mock A's timeline, Tobi 23.10.2026): the phases one
	// below the other on a line that tells how the run went (green, yellow where something is
	// uncertain, red where something failed, dashed from what still waits on), the steps as the
	// cards of the log before, the four signals two by two. A card opens its details below it.
	let {
		groups,
		run,
		selected,
		summaryOf,
		durationOf,
		phaseDuration,
		highlighted = null,
		onhighlight,
		ontoggle,
		details
	}: StepsProps = $props();

	type Line = 'green' | 'yellow' | 'red' | 'running' | 'waiting';

	function lineOf(steps: readonly Step[]): Line {
		const own = steps.filter((step) => step.state !== null && step.state.status !== 'skipped');
		if (own.some((step) => step.state?.outcome === 'failed')) return 'red';
		if (own.some((step) => step.state?.outcome === 'uncertain')) return 'yellow';
		if (own.some((step) => step.state !== null && isAtWork(step.state))) return 'running';
		if (own.length === 0 || own.every((step) => step.state?.status === 'waiting')) return 'waiting';
		return 'green';
	}

	// From the first phase with a waiting step on, the line is dashed: that part is still ahead.
	// That phase's dot too, unless something in it is uncertain, failed or running.
	const lines = $derived.by(() => {
		const tones = groups.map((group) => lineOf(group.steps));
		const waiting = groups.findIndex((group) =>
			group.steps.some((step) => step.state?.status === 'waiting')
		);
		return tones.map((tone, index) => ({
			dot:
				waiting !== -1 && (index > waiting || (index === waiting && tone === 'green'))
					? 'waiting'
					: tone,
			dashed: waiting !== -1 && index >= waiting
		}));
	});

	const dots: Record<Line, string> = {
		green: TONE_DOT.green,
		yellow: TONE_DOT.yellow,
		red: TONE_DOT.red,
		running: cn('motion-safe:animate-pulse', TONE_DOT.running),
		waiting: 'border-2 border-dashed border-muted-foreground'
	};
	const rails: Record<Line, string> = {
		green: 'bg-lane-green-foreground/45',
		yellow: 'bg-lane-yellow-foreground/55',
		red: 'bg-lane-red-foreground/50',
		running: 'bg-lane-running-foreground/50',
		waiting: 'bg-muted-foreground/40'
	};
	const panelId = (node: Node) => `step-details-${node}`;
</script>

{#snippet panel(step: Step)}
	<div
		id={panelId(step.node)}
		class={cn(
			'rounded-2xl border p-3.5',
			STEP_BORDER[stepLook(step.state).tone],
			STEP_TINT[stepLook(step.state).tone]
		)}
	>
		{@render details(step)}
	</div>
{/snippet}

<section aria-labelledby="steps-heading" class="flex min-w-0 flex-col">
	<SectionTitle size="card" id="steps-heading" class="mb-3">
		{m.processing_steps()} · {m.log_run({ run })}
	</SectionTitle>
	{#each groups as group, index (group.phase)}
		{@const line = lines[index]}
		{@const last = index === groups.length - 1}
		{@const grid = group.phase === 'recognise'}
		<div class="grid grid-cols-[1.5rem_minmax(0,1fr)] gap-x-3">
			<div class="flex flex-col items-center" aria-hidden="true">
				<span class={cn('mt-0.5 size-3.5 shrink-0 rounded-full', dots[line.dot])}></span>
				{#if !last}
					{#if line.dashed}
						<span class="mt-1 w-0 flex-1 border-l-[3px] border-dashed border-muted-foreground/40"
						></span>
					{:else}
						<span class={cn('mt-1 w-[3px] flex-1 rounded-full', rails[line.dot])}></span>
					{/if}
				{/if}
			</div>
			<div class={cn('flex min-w-0 flex-col gap-2', !last && 'pb-5')}>
				<Eyebrow as="h3" class="tracking-wider whitespace-nowrap">
					{PHASE_LABELS[group.phase]()}{#if phaseDuration(group.steps)}<span
							class="tracking-normal normal-case">{` · ${phaseDuration(group.steps)}`}</span
						>{/if}
				</Eyebrow>
				<div class={grid ? 'grid grid-cols-2 gap-2' : 'flex flex-col gap-2'}>
					{#each group.steps as step (step.node)}
						<StepCard
							{step}
							summary={summaryOf(step)}
							duration={durationOf(step)}
							expanded={step.node === selected}
							highlighted={step.node === highlighted}
							onhighlight={(on) => onhighlight(on ? step.node : null)}
							controls={panelId(step.node)}
							compact={grid}
							onclick={() => ontoggle(step.node)}
						/>
						{#if !grid && step.node === selected}{@render panel(step)}{/if}
					{/each}
				</div>
				{#if grid}
					{@const open = group.steps.find((step) => step.node === selected)}
					{#if open}{@render panel(open)}{/if}
				{/if}
			</div>
		</div>
	{/each}
</section>
