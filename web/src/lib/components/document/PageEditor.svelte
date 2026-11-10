<script lang="ts">
	import FileOutput from '@lucide/svelte/icons/file-output';
	import FilePlus from '@lucide/svelte/icons/file-plus';
	import Redo2 from '@lucide/svelte/icons/redo-2';
	import RotateCcw from '@lucide/svelte/icons/rotate-ccw';
	import RotateCw from '@lucide/svelte/icons/rotate-cw';
	import Trash2 from '@lucide/svelte/icons/trash-2';
	import Undo2 from '@lucide/svelte/icons/undo-2';
	import { tick, untrack } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { api } from '#lib/api/client.ts';
	import { apiError } from '#lib/api/problem.ts';
	import type { components } from '#lib/api/schema.ts';
	import EditorShell from '#lib/components/EditorShell.svelte';
	import IconButton from '#lib/components/IconButton.svelte';
	import PageCut from '#lib/components/pages/PageCut.svelte';
	import PageImage from '#lib/components/pages/PageImage.svelte';
	import PageTile from '#lib/components/pages/PageTile.svelte';
	import Segmented from '#lib/components/Segmented.svelte';
	import SelectionBar from '#lib/components/SelectionBar.svelte';
	import * as Alert from '#lib/components/ui/alert/index.ts';
	import { Badge } from '#lib/components/ui/badge/index.ts';
	import { Button } from '#lib/components/ui/button/index.ts';
	import * as Card from '#lib/components/ui/card/index.ts';
	import { pageImageHref } from '#lib/document-view.ts';
	import { describeError } from '#lib/errors.ts';
	import { GRID_KEYS, nextTile } from '#lib/grid-keys.ts';
	import {
		History,
		addPages,
		moveTo,
		partRanges,
		partsOf,
		partsRequest,
		remove,
		splitOff,
		startStack,
		toggleCut,
		turn,
		unchanged,
		type Stack
	} from '#lib/page-edit.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { phone } from '#lib/phone.svelte.ts';

	type Document = components['schemas']['DocumentDetails'];
	type Edited = components['schemas']['EditedDocuments'];

	// "PDF bearbeiten" (web/DESIGN.md, "Page tile", "Page cut"; `POST /documents/{id}/edit`):
	// first the stack of the document's pages, to choose, turn, remove, reorder (dragging, or
	// Ctrl + arrow), cut into parts and add the pages of a file from the device to; then the
	// parts, each replacing the document or becoming a new one. Nothing is stored before
	// "Übernehmen"; every result waits in the inbox.
	let {
		open = $bindable(false),
		document,
		onedited
	}: {
		open?: boolean;
		document: Document;
		/** After the edit, with the documents it left. */
		onedited: (edited: Edited) => void;
	} = $props();

	/** How long a finger rests on a page before it can be moved. */
	const LONG_PRESS = 400;

	let history = new History([]);
	let stack = $state<Stack>([]);
	let canUndo = $state(false);
	let canRedo = $state(false);
	let chosen = $state<ReadonlySet<string>>(new Set());
	let anchor: string | null = null;
	let focused = $state<string | null>(null);
	let step = $state<'pages' | 'parts'>('pages');
	let replacing = $state<number | null>(0);
	let added = $state<File[]>([]);
	let adding = $state(false);
	let picker = $state<HTMLInputElement | null>(null);
	let grid = $state<HTMLElement | null>(null);

	const count = $derived(document.page_count ?? 0);
	const parts = $derived(partsOf(stack));
	const ranges = $derived(partRanges(stack));
	const nothing = $derived(stack.length === 0 || unchanged(stack, count));
	const stop = $derived(
		focused && stack.some((page) => page.key === focused) ? focused : (stack[0]?.key ?? null)
	);
	const title = $derived(m.page_edit_title({ title: document.title }));

	let shown = false;
	$effect(() => {
		if (open && !shown) untrack(reset);
		shown = open;
	});

	function reset() {
		history = new History(startStack(count, (page) => pageImageHref(document.id, page)));
		chosen = new Set();
		anchor = null;
		focused = null;
		step = 'pages';
		replacing = 0;
		added = [];
		sync();
	}

	function sync() {
		stack = history.current;
		canUndo = history.canUndo;
		canRedo = history.canRedo;
		const there = new Set(stack.map((page) => page.key));
		if ([...chosen].some((key) => !there.has(key))) {
			chosen = new Set([...chosen].filter((key) => there.has(key)));
		}
	}

	function change(next: Stack) {
		history.push(next);
		sync();
	}

	function undo() {
		history.undo();
		sync();
	}

	function redo() {
		history.redo();
		sync();
	}

	const place = (key: string) => stack.findIndex((page) => page.key === key);

	function choose(key: string, range: boolean) {
		if (range && anchor !== null && place(anchor) >= 0) {
			const [from, to] = [place(anchor), place(key)].sort((a, b) => a - b);
			const span = stack.slice(from, to + 1).map((page) => page.key);
			chosen = new Set([...chosen, ...span]);
		} else {
			chosen = new Set(
				chosen.has(key) ? [...chosen].filter((item) => item !== key) : [...chosen, key]
			);
			anchor = key;
		}
		focused = key;
	}

	function act(make: (stack: Stack, keys: ReadonlySet<string>) => Stack, keep = true) {
		change(make(stack, chosen));
		if (!keep) chosen = new Set();
	}

	// --- the keyboard: one tab stop, the arrows move it, Ctrl + arrow moves the page ---------

	function boxes(): HTMLInputElement[] {
		return [...(grid?.querySelectorAll<HTMLInputElement>('[data-page-tile] input') ?? [])];
	}

	async function focusPage(key: string) {
		focused = key;
		await tick();
		boxes()[place(key)]?.focus();
	}

	function keydown(event: KeyboardEvent, index: number) {
		const key = stack[index].key;
		if (event.key === 'Enter') {
			// A cut after this page; never the form's submit.
			event.preventDefault();
			if (index < stack.length - 1) change(toggleCut(stack, index + 1));
			return;
		}
		if (!GRID_KEYS.has(event.key)) return;
		event.preventDefault();
		const moving = event.ctrlKey || event.metaKey;
		const rects = boxes().map((box) => box.closest('[data-page-tile]')!.getBoundingClientRect());
		const target = nextTile(event.key, index, rects, moving);
		if (target === null) return;
		if (moving) change(moveTo(stack, new Set([key]), target));
		void focusPage(moving ? key : stack[target].key);
	}

	// --- moving by dragging: a mouse at once, a finger after resting on the page ---------------

	let press: { key: string; x: number; y: number; touch: boolean; armed: boolean } | null = null;
	let timer: ReturnType<typeof setTimeout> | undefined;
	let drag = $state<{ keys: ReadonlySet<string>; at: number } | null>(null);
	let swallow = false;

	function pointerdown(event: PointerEvent, key: string) {
		if (event.button !== 0 || (event.target as HTMLElement).closest('input')) return;
		const touch = event.pointerType === 'touch';
		press = { key, x: event.clientX, y: event.clientY, touch, armed: !touch };
		if (touch) timer = setTimeout(() => press && (press.armed = true), LONG_PRESS);
		window.addEventListener('pointermove', pointermove);
		window.addEventListener('pointerup', pointerup);
		window.addEventListener('pointercancel', release);
	}

	function pointermove(event: PointerEvent) {
		if (!press) return;
		const distance = Math.hypot(event.clientX - press.x, event.clientY - press.y);
		if (!drag) {
			// A finger that moves before it rested scrolls.
			if (!press.armed) {
				if (distance > 8) release();
				return;
			}
			if (distance < 6) return;
			const keys = chosen.has(press.key) ? chosen : new Set([press.key]);
			drag = { keys, at: place(press.key) };
		}
		drag = { ...drag, at: dropAt(event.clientX, event.clientY) };
	}

	/** Where a page let go at a point lands: before or after the nearest page. */
	function dropAt(x: number, y: number): number {
		const tiles = [...(grid?.querySelectorAll('[data-page-tile]') ?? [])];
		let best = 0;
		let nearest = Infinity;
		tiles.forEach((tile, index) => {
			const box = tile.getBoundingClientRect();
			const distance = Math.hypot(box.left + box.width / 2 - x, box.top + box.height / 2 - y);
			if (distance < nearest) [best, nearest] = [index, distance];
		});
		const box = tiles[best]?.getBoundingClientRect();
		return box && x > box.left + box.width / 2 ? best + 1 : best;
	}

	function pointerup() {
		if (drag) {
			const { keys, at } = drag;
			const before = stack.slice(0, at).filter((page) => !keys.has(page.key)).length;
			change(moveTo(stack, keys, before));
			swallowClick();
		} else if (press?.touch && press.armed) {
			// A finger that rested without moving chooses.
			choose(press.key, false);
			swallowClick();
		}
		release();
	}

	function release() {
		clearTimeout(timer);
		press = null;
		drag = null;
		window.removeEventListener('pointermove', pointermove);
		window.removeEventListener('pointerup', pointerup);
		window.removeEventListener('pointercancel', release);
	}

	/** The click after a move or a long press is no choice. */
	function swallowClick() {
		swallow = true;
		setTimeout(() => (swallow = false), 50);
	}

	// A finger that rested moves the page instead of scrolling the dialog.
	$effect(() => {
		const element = grid;
		if (!element) return;
		const hold = (event: TouchEvent) => {
			if (press?.armed) event.preventDefault();
		};
		element.addEventListener('touchmove', hold, { passive: false });
		return () => element.removeEventListener('touchmove', hold);
	});

	// --- adding the pages of a file -------------------------------------------------------------

	async function add(file: File) {
		adding = true;
		try {
			const form = new FormData();
			form.append('file', file, file.name);
			const { data, error, response } = await api.POST('/api/v1/documents/{id}/edit/pages', {
				params: { path: { id: document.id } },
				// The generated type wants a string for the file; the form carries the binary.
				body: { file: '' },
				bodySerializer: () => form
			});
			if (!data) throw await apiError(response, error);
			added = [...added, file];
			const source = added.length;
			const last = stack.reduce((at, page, index) => (chosen.has(page.key) ? index : at), -1);
			change(addPages(stack, source, data.pages, last >= 0 ? last : null));
			chosen = new Set(data.pages.map((_, index) => `${source}:${index + 1}`));
			toast.success(m.page_edit_added({ count: data.pages.length, file: file.name }));
		} catch (problem) {
			toast.error(describeError(problem));
		} finally {
			adding = false;
		}
	}

	// --- the steps --------------------------------------------------------------------------------

	async function submit() {
		if (step === 'pages') {
			if (replacing !== null && replacing >= parts.length) replacing = 0;
			step = 'parts';
			return;
		}
		const form = new FormData();
		form.append('parts', JSON.stringify(partsRequest(stack, replacing)));
		for (const file of added) form.append('files', file, file.name);
		const { data, error, response } = await api.POST('/api/v1/documents/{id}/edit', {
			params: { path: { id: document.id } },
			body: { parts: '' },
			bodySerializer: () => form
		});
		if (!data) throw await apiError(response, error);
		open = false;
		onedited(data);
	}

	const selected = $derived(
		chosen.size === 1 ? m.page_edit_chosen_one() : m.page_edit_chosen({ count: chosen.size })
	);
	const pagesOf = ([first, last]: [number, number]) =>
		first === last
			? m.page_edit_part_page({ page: String(first) })
			: m.page_edit_part_pages({ first: String(first), last: String(last) });
</script>

<EditorShell
	bind:open
	{title}
	shortTitle={m.page_edit_short()}
	description={step === 'pages'
		? m.page_edit_pages_hint({ count: stack.length })
		: m.page_edit_parts_hint({ count: parts.length })}
	size="xl"
	fixed
	stay={step === 'pages'}
	back={step === 'parts' ? () => (step = 'pages') : undefined}
	submitLabel={step === 'pages'
		? parts.length === 1
			? m.page_edit_next()
			: m.page_edit_next_parts({ count: parts.length })
		: m.page_edit_apply()}
	shortSubmitLabel={step === 'pages' ? m.page_edit_next() : m.page_edit_apply()}
	disabled={nothing || adding}
	action={submit}
>
	{#if step === 'pages'}
		<div class="flex flex-wrap items-center gap-2">
			<div class="flex flex-1 flex-wrap gap-1.5" aria-label={m.page_edit_parts()}>
				{#each ranges as range, index (index)}
					<Badge variant="muted">
						{m.page_edit_part({ number: String(index + 1) })} · {pagesOf(range)}
					</Badge>
				{/each}
			</div>
			<Button
				type="button"
				variant="outline"
				size="sm"
				disabled={adding}
				onclick={() => picker?.click()}
			>
				<FilePlus aria-hidden="true" />
				{m.page_edit_add()}
			</Button>
			<input
				bind:this={picker}
				type="file"
				accept="application/pdf,image/jpeg,image/png,image/tiff"
				class="hidden"
				aria-hidden="true"
				tabindex="-1"
				onchange={(event) => {
					const file = event.currentTarget.files?.[0];
					event.currentTarget.value = '';
					if (file) void add(file);
				}}
			/>
			<IconButton size="sm" label={m.page_edit_undo()} disabled={!canUndo} onclick={undo}>
				<Undo2 aria-hidden="true" />
			</IconButton>
			<IconButton size="sm" label={m.page_edit_redo()} disabled={!canRedo} onclick={redo}>
				<Redo2 aria-hidden="true" />
			</IconButton>
		</div>

		{#snippet bar()}
			<SelectionBar count={selected} inDialog>
				{#snippet trail()}
					<Button type="button" variant="ghost" size="sm" onclick={() => (chosen = new Set())}>
						{m.page_edit_clear()}
					</Button>
				{/snippet}
				{#snippet actions()}
					<Button
						type="button"
						variant="outline"
						size="sm"
						onclick={() => act((s, k) => turn(s, k, -90))}
					>
						<RotateCcw aria-hidden="true" />
						{phone.current ? m.page_edit_left_short() : m.page_edit_left()}
					</Button>
					<Button
						type="button"
						variant="outline"
						size="sm"
						onclick={() => act((s, k) => turn(s, k, 90))}
					>
						<RotateCw aria-hidden="true" />
						{phone.current ? m.page_edit_right_short() : m.page_edit_right()}
					</Button>
					<Button type="button" variant="outline" size="sm" onclick={() => act(remove, false)}>
						<Trash2 aria-hidden="true" />
						{m.page_edit_remove()}
					</Button>
					<Button type="button" variant="outline" size="sm" onclick={() => act(splitOff, false)}>
						<FileOutput aria-hidden="true" />
						{phone.current ? m.page_edit_split_short() : m.page_edit_split()}
					</Button>
				{/snippet}
			</SelectionBar>
		{/snippet}

		{#if chosen.size > 0 && !phone.current}{@render bar()}{/if}

		<!-- The clicks after a move or a long press are swallowed before the tiles see them. -->
		<div
			bind:this={grid}
			role="group"
			aria-label={m.page_edit_stack()}
			class="flex flex-wrap items-stretch gap-y-3"
			onclickcapture={(event) => {
				if (swallow) {
					event.preventDefault();
					event.stopPropagation();
				}
			}}
		>
			{#each stack as page, index (page.key)}
				<div class="flex">
					<PageTile
						image={page.image}
						rotate={page.rotate}
						label={m.page_edit_page({ page: String(index + 1) })}
						chosen={chosen.has(page.key)}
						ghost={drag?.keys.has(page.key) ?? false}
						tabindex={page.key === stop ? 0 : -1}
						onchoose={(range) => choose(page.key, range)}
						onkeydown={(event) => keydown(event, index)}
						onfocus={() => (focused = page.key)}
						onpointerdown={(event) => pointerdown(event, page.key)}
						oncontextmenu={(event) => {
							if (press?.touch) event.preventDefault();
						}}
					/>
					{#if index < stack.length - 1}
						<PageCut
							after={index + 1}
							cut={stack[index + 1].cut}
							target={drag?.at === index + 1}
							ontoggle={() => change(toggleCut(stack, index + 1))}
						/>
					{/if}
				</div>
			{/each}
		</div>
		<p class="text-meta text-muted-foreground">{m.page_edit_legend()}</p>

		{#if chosen.size > 0 && phone.current}{@render bar()}{/if}
	{:else}
		{#each parts as part, index (index)}
			<Card.Root size="row" class="flex items-start gap-3">
				<div class="flex shrink-0 gap-1" aria-hidden="true">
					{#each part.slice(0, 2) as page (page.key)}
						<PageImage src={page.image} class="max-h-14 max-w-11 rounded-sm border bg-card" />
					{/each}
				</div>
				<div class="flex min-w-0 flex-col gap-2">
					<span class="flex flex-wrap items-center gap-2 font-medium">
						{m.page_edit_part({ number: String(index + 1) })}
						<Badge variant="muted">{pagesOf(ranges[index])}</Badge>
					</span>
					<Segmented
						size="sm"
						label={m.page_edit_part({ number: String(index + 1) })}
						value={replacing === index ? 'replace' : 'new'}
						options={[
							{ value: 'replace', label: m.page_edit_replaces({ title: document.title }) },
							{ value: 'new', label: m.page_edit_new() }
						]}
						onchange={(value) => {
							if (value === 'replace') replacing = index;
							else if (replacing === index) replacing = null;
						}}
					/>
				</div>
			</Card.Root>
		{/each}
		<Alert.Root variant="note">
			<Alert.Description>
				{m.page_edit_inbox()}
				{replacing === null
					? m.page_edit_deleted({ title: document.title })
					: m.page_edit_kept({
							title: document.title,
							part: String(replacing + 1)
						})}
			</Alert.Description>
		</Alert.Root>
	{/if}
</EditorShell>
