<script lang="ts">
	import ChevronDown from '@lucide/svelte/icons/chevron-down';
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
	import DocumentChoice from '#lib/components/document/DocumentChoice.svelte';
	import SelectionChooser from '#lib/components/SelectionChooser.svelte';
	import BeamTitle from '#lib/components/BeamTitle.svelte';
	import { showPages, type BeamPart } from '#lib/beam.svelte.ts';
	import EditorShell from '#lib/components/EditorShell.svelte';
	import IconButton from '#lib/components/IconButton.svelte';
	import PageCut from '#lib/components/pages/PageCut.svelte';
	import PageImage from '#lib/components/pages/PageImage.svelte';
	import PageTile from '#lib/components/pages/PageTile.svelte';
	import Segmented from '#lib/components/Segmented.svelte';
	import Select from '#lib/components/Select.svelte';
	import SelectionBar from '#lib/components/SelectionBar.svelte';
	import SidewaysRow from '#lib/components/SidewaysRow.svelte';
	import * as Alert from '#lib/components/ui/alert/index.ts';
	import { Badge } from '#lib/components/ui/badge/index.ts';
	import { Button } from '#lib/components/ui/button/index.ts';
	import * as Card from '#lib/components/ui/card/index.ts';
	import * as DropdownMenu from '#lib/components/ui/dropdown-menu/index.ts';
	import * as Field from '#lib/components/ui/field/index.ts';
	import { pageImageHref } from '#lib/document-view.ts';
	import { describeError } from '#lib/errors.ts';
	import { GRID_KEYS, nextTile } from '#lib/grid-keys.ts';
	import { listLocale, quoted } from '#lib/i18n.ts';
	import type { Candidate, Mergeable } from '#lib/merge.ts';
	import {
		History,
		addPages,
		markOf,
		moveTo,
		partRanges,
		partsOf,
		partsRequest,
		remove,
		requestPlaces,
		sourcesOn,
		splitOff,
		startStack,
		toggleCut,
		turn,
		unchanged,
		type Stack
	} from '#lib/page-edit.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { phone } from '#lib/phone.svelte.ts';

	type Edited = components['schemas']['EditedDocuments'];
	/** What was added: a file from the device, or another document (a merge). */
	type Source = { file: File } | { document: Mergeable };

	// "PDF bearbeiten" (web/DESIGN.md, "Page tile", "Page cut", "Page stack"; `POST
	// /documents/{id}/edit`): first the stack of the document's pages, to choose, turn, remove,
	// reorder (dragging, or Ctrl + arrow), cut into parts and add the pages of a file from the
	// device or of another document to; then the parts, each replacing the document or becoming a
	// new one. With other documents' pages it merges them ("2 Dokumente zusammenführen"): each
	// page carries its document's letter, and one part becomes the next version of the document
	// chosen as "Neue Fassung von" (it must: else every original would go). Nothing is stored
	// before "Übernehmen"; every result waits in the inbox.
	let {
		open = $bindable(false),
		document,
		mergeWith = [],
		onedited
	}: {
		open?: boolean;
		document: Mergeable;
		/** Documents whose pages are on the stack from the start (merging from the list). */
		mergeWith?: readonly Mergeable[];
		/** After the edit, with the documents it left and the one a part replaced (null: none,
		 * the document is gone). */
		onedited: (edited: Edited, target: string | null) => void;
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
	let sources = $state<Source[]>([]);
	let adding = $state(false);
	let picker = $state<HTMLInputElement | null>(null);
	let picking = $state(false);
	/** The document the part that replaces makes the next version of, in a merge. */
	let target = $state('');
	let grid = $state<HTMLElement | null>(null);
	/** The number the next version gets, once the document's versions are known. */
	let nextVersion = $state<number | null>(null);

	const count = $derived(document.page_count ?? 0);
	const parts = $derived(partsOf(stack));
	const ranges = $derived(partRanges(stack));
	/** The added sources with a page on the stack: one undone or emptied is no part of the edit
	 * (a document of it is not merged, and can be chosen again). */
	const used = $derived(sourcesOn(stack));
	const files = $derived(
		sources.flatMap((source, index) =>
			'file' in source && used.has(index + 1) ? [source.file] : []
		)
	);
	const others = $derived(
		sources.flatMap((source, index) =>
			'document' in source && used.has(index + 1) ? [source.document] : []
		)
	);
	/** The documents whose pages are on the stack (A, B, …): a merge with more than one. */
	const documents = $derived([document, ...others]);
	const merging = $derived(others.length > 0);
	const nothing = $derived(stack.length === 0 || (!merging && unchanged(stack, count)));
	const stop = $derived(
		focused && stack.some((page) => page.key === focused) ? focused : (stack[0]?.key ?? null)
	);
	const title = $derived(
		merging
			? m.merge_title({ count: String(documents.length) })
			: m.page_edit_title({ title: document.title })
	);

	let shown = false;
	$effect(() => {
		if (open && !shown) untrack(reset);
		shown = open;
	});

	function reset() {
		let start = startStack(count, (page) => pageImageHref(document.id, page));
		mergeWith.forEach((other, index) => {
			start = addPages(start, index + 1, imagesOf(other), null);
		});
		history = new History(start);
		chosen = new Set();
		anchor = null;
		focused = null;
		step = 'pages';
		replacing = 0;
		sources = mergeWith.map((other) => ({ document: other }));
		target = document.id;
		nextVersion = null;
		sync();
		void api
			.GET('/api/v1/documents/{id}/files', { params: { path: { id: document.id } } })
			.then(({ data }) => {
				if (data) nextVersion = data.versions.length + 1;
			})
			.catch(() => {});
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

	function chooseAll() {
		chosen = new Set(stack.map((page) => page.key));
	}

	// --- the Beam: the parts as they are to be, before anything is stored -----------------------

	/** The parts for the Beam (`showPages`): each its pages, turned; in the second step what it
	 * becomes. */
	function beamParts(): BeamPart[] {
		return parts.map((part, index) => {
			const becomes =
				step === 'parts' ? (replacing === index ? m.page_edit_version() : m.page_edit_new()) : null;
			return {
				title: m.page_edit_part({ number: String(index + 1) }),
				meta: [pagesOf(ranges[index]), becomes].filter(Boolean).join(' · '),
				pages: part.map((page) => ({ src: page.image, turn: page.rotate }))
			};
		});
	}

	/** Show the page at `place` (from 0) of the stack in the Beam, among the parts. */
	function showPage(place: number) {
		let before = 0;
		const index = parts.findIndex((part) => {
			if (place < before + part.length) return true;
			before += part.length;
			return false;
		});
		showPages(beamParts(), Math.max(index, 0), title, place - before + 1);
	}

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
		if (event.key.toLowerCase() === 'b' && !event.ctrlKey && !event.metaKey && !event.altKey) {
			event.preventDefault();
			showPage(index);
			return;
		}
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
		if (event.button !== 0 || (event.target as HTMLElement).closest('input, button')) return;
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
			put({ file }, data.pages);
			toast.success(m.page_edit_added({ count: data.pages.length, file: file.name }));
		} catch (problem) {
			toast.error(describeError(problem));
		} finally {
			adding = false;
		}
	}

	/** The pages of another document joined to the stack (a merge). */
	function addDocument(other: Candidate) {
		put({ document: other }, imagesOf(other));
	}

	/** The pages of `source` put after the last chosen page (at the end without one), chosen. */
	function put(source: Source, images: readonly string[]) {
		sources = [...sources, source];
		const number = sources.length;
		const last = stack.reduce((at, page, index) => (chosen.has(page.key) ? index : at), -1);
		change(addPages(stack, number, images, last >= 0 ? last : null));
		chosen = new Set(images.map((_, index) => `${number}:${index + 1}`));
	}

	function imagesOf(other: Mergeable): string[] {
		return Array.from({ length: other.page_count ?? 0 }, (_, index) =>
			pageImageHref(other.id, index + 1)
		);
	}

	/** The document a page of the stack comes from; null for a file's. */
	function documentOf(source: number): Mergeable | null {
		if (source === 0) return document;
		const added = sources[source - 1];
		return added && 'document' in added ? added.document : null;
	}

	/** The letter of the document a page comes from, in a merge. */
	function markFor(source: number): string | undefined {
		const from = merging ? documentOf(source) : null;
		return from ? markOf(documents.indexOf(from)) : undefined;
	}

	/** The name of a page's box in a merge: its place and its document. */
	function nameFor(source: number, place: number): string | undefined {
		const from = merging ? documentOf(source) : null;
		return from ? m.page_edit_page_from({ page: String(place), title: from.title }) : undefined;
	}

	// --- the steps --------------------------------------------------------------------------------

	async function submit() {
		if (step === 'pages') {
			if (replacing !== null && replacing >= parts.length) replacing = 0;
			// A document whose pages left the stack is merged no more, nor continued.
			if (!documents.some((item) => item.id === target)) target = document.id;
			step = 'parts';
			return;
		}
		const form = new FormData();
		const place = requestPlaces(
			sources.map((source) => 'file' in source),
			used
		);
		form.append('parts', JSON.stringify(partsRequest(stack, replacing, place)));
		for (const file of files) form.append('files', file, file.name);
		if (merging) {
			form.append('documents', JSON.stringify(others.map((other) => other.id)));
			if (target !== document.id) form.append('target', target);
		}
		const { data, error, response } = await api.POST('/api/v1/documents/{id}/edit', {
			params: { path: { id: document.id } },
			body: { parts: '' },
			bodySerializer: () => form
		});
		if (!data) throw await apiError(response, error);
		open = false;
		onedited(data, replacing === null ? null : merging ? target : document.id);
	}

	const selected = $derived(
		chosen.size === 0
			? m.page_edit_none()
			: chosen.size === 1
				? m.page_edit_chosen_one()
				: m.page_edit_chosen({ count: chosen.size })
	);
	const pagesOf = ([first, last]: [number, number]) =>
		first === last
			? m.page_edit_part_page({ page: String(first) })
			: m.page_edit_part_pages({ first: String(first), last: String(last) });
	const pageCount = $derived(
		stack.length === 1 ? m.page_edit_pages_one() : m.page_edit_pages({ count: stack.length })
	);
	const partCount = $derived(
		parts.length === 1 ? m.page_edit_parts_one() : m.page_edit_parts_count({ count: parts.length })
	);
	/** What becomes of each part, in words (the note of the second step). */
	const outcome = $derived.by(() => {
		if (merging) return merged();
		const runs =
			parts.length === 1
				? m.page_edit_inbox_one()
				: parts.length === 2
					? m.page_edit_inbox_two()
					: m.page_edit_inbox();
		const fresh = parts.map((_, index) => index).filter((index) => index !== replacing);
		const names = new Intl.ListFormat(listLocale(), { type: 'conjunction' }).format(
			fresh.map((index) => String(index + 1))
		);
		const kept =
			replacing === null
				? m.page_edit_deleted({ title: document.title })
				: nextVersion === null
					? m.page_edit_kept_any({ part: String(replacing + 1), title: document.title })
					: m.page_edit_kept({
							part: String(replacing + 1),
							version: String(nextVersion),
							title: document.title
						});
		const others =
			fresh.length === 0 || replacing === null
				? ''
				: fresh.length === 1
					? m.page_edit_new_one({ part: names })
					: m.page_edit_new_many({ parts: names });
		return [runs, kept, others].filter(Boolean).join(' ');
	});

	/** What a merge makes of each document, in words; it needs a part that replaces. */
	function merged(): string {
		if (replacing === null) return m.merge_needs_target();
		const goal = documents.find((item) => item.id === target) ?? document;
		const gone = documents.filter((item) => item.id !== goal.id);
		const list = (items: string[]) =>
			new Intl.ListFormat(listLocale(), { type: 'conjunction' }).format(items);
		const kept = m.merge_kept({ part: String(replacing + 1), title: goal.title });
		const lost =
			gone.length === 1
				? m.merge_gone_one({ title: gone[0].title, target: goal.title })
				: m.merge_gone_many({
						titles: list(gone.map((item) => quoted(item.title))),
						target: goal.title
					});
		const fresh = parts.map((_, index) => index).filter((index) => index !== replacing);
		const names = list(fresh.map((index) => String(index + 1)));
		const split =
			fresh.length === 0
				? ''
				: fresh.length === 1
					? m.page_edit_new_one({ part: names })
					: m.page_edit_new_many({ parts: names });
		const runs = parts.length === 1 ? m.page_edit_inbox_one() : m.page_edit_inbox();
		return [kept, lost, split, runs].filter(Boolean).join(' ');
	}

	const targets = $derived(
		documents.map((item, index) => ({
			value: item.id,
			label: m.page_edit_source({ mark: markOf(index), title: item.title })
		}))
	);
</script>

{#snippet pageActions()}
	{@const size = phone.current ? 'stack' : 'sm'}
	{@const none = chosen.size === 0}
	<Button
		type="button"
		variant="outline"
		{size}
		disabled={none}
		onclick={() => act((s, k) => turn(s, k, -90))}
	>
		<RotateCcw aria-hidden="true" />
		{m.page_edit_left_short()}
	</Button>
	<Button
		type="button"
		variant="outline"
		{size}
		disabled={none}
		onclick={() => act((s, k) => turn(s, k, 90))}
	>
		<RotateCw aria-hidden="true" />
		{m.page_edit_right_short()}
	</Button>
	<Button type="button" variant="outline" {size} disabled={none} onclick={() => act(remove, false)}>
		<Trash2 aria-hidden="true" />
		{m.page_edit_remove()}
	</Button>
	<Button
		type="button"
		variant="outline"
		{size}
		disabled={none}
		onclick={() => act(splitOff, false)}
	>
		<FileOutput aria-hidden="true" />
		{m.page_edit_split_short()}
	</Button>
{/snippet}

{#snippet bar()}
	<!-- As the documents list's (web/DESIGN.md, "Choosing many"): "Auswählen" before the count,
	the tools after it, nothing that comes or goes as the choice changes. -->
	<SelectionBar
		count={selected}
		inDialog
		lead={phone.current ? undefined : chooser}
		trail={phone.current ? chooser : undefined}
	>
		{#snippet actions()}{@render pageActions()}{/snippet}
	</SelectionBar>
{/snippet}

{#snippet chooser()}
	<SelectionChooser disabled={stack.length === 0}>
		<DropdownMenu.Item disabled={chosen.size === stack.length} onSelect={chooseAll}>
			{m.page_edit_select_all()}
		</DropdownMenu.Item>
		<DropdownMenu.Item disabled={chosen.size === 0} onSelect={() => (chosen = new Set())}>
			{m.bulk_select_none()}
		</DropdownMenu.Item>
	</SelectionChooser>
{/snippet}

{#snippet tools()}
	<div class="flex items-center gap-2">
		{#if !phone.current}
			<SidewaysRow label={m.page_edit_parts()} class="flex-1">
				{@render partBadges()}
			</SidewaysRow>
		{/if}
		<DropdownMenu.Root>
			<DropdownMenu.Trigger disabled={adding}>
				{#snippet child({ props })}
					<Button
						{...props}
						type="button"
						variant="outline"
						size={phone.current ? 'default' : 'sm'}
					>
						<FilePlus aria-hidden="true" />
						{m.page_edit_add()}
						<ChevronDown aria-hidden="true" />
					</Button>
				{/snippet}
			</DropdownMenu.Trigger>
			<DropdownMenu.Content align="end" class="w-56">
				<DropdownMenu.Item onSelect={() => picker?.click()}>
					{m.page_edit_add_file()}
				</DropdownMenu.Item>
				<DropdownMenu.Item onSelect={() => (picking = true)}>
					{m.page_edit_add_document()}
				</DropdownMenu.Item>
			</DropdownMenu.Content>
		</DropdownMenu.Root>
		{#if phone.current}<span class="flex-1"></span>{/if}
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
		<IconButton
			size={phone.current ? 'default' : 'sm'}
			label={m.page_edit_undo()}
			disabled={!canUndo}
			onclick={undo}
		>
			<Undo2 aria-hidden="true" />
		</IconButton>
		<IconButton
			size={phone.current ? 'default' : 'sm'}
			label={m.page_edit_redo()}
			disabled={!canRedo}
			onclick={redo}
		>
			<Redo2 aria-hidden="true" />
		</IconButton>
	</div>
	{#if merging}
		<SidewaysRow label={m.page_edit_sources()}>
			<span class="mr-1 text-meta text-muted-foreground">{m.page_edit_sources()}</span>
			{#each documents as item, index (item.id)}
				<Badge variant="outline">
					{m.page_edit_source({ mark: markOf(index), title: item.title })}
				</Badge>
			{/each}
		</SidewaysRow>
	{/if}
	{#if phone.current}
		<SidewaysRow label={m.page_edit_parts()}>
			<span class="mr-1 text-meta text-muted-foreground">{pageCount}</span>
			{@render partBadges()}
		</SidewaysRow>
	{:else}
		{@render bar()}
	{/if}
{/snippet}

{#snippet partBadges()}
	{#each ranges as range, index (index)}
		<Badge variant="muted">
			{m.page_edit_part({ number: String(index + 1) })} · {pagesOf(range)}
		</Badge>
	{/each}
{/snippet}

{#snippet phoneBottom()}
	{#if chosen.size > 0}
		{@render bar()}
	{:else}
		<p
			class="border-t bg-card px-4 pt-3 pb-[max(1rem,calc(env(safe-area-inset-bottom)+0.5rem))] text-sm text-muted-foreground"
		>
			{m.page_edit_phone_hint()}
		</p>
	{/if}
{/snippet}

<EditorShell
	bind:open
	{title}
	shortTitle={merging ? m.merge_short() : m.page_edit_short()}
	description={phone.current
		? step === 'parts'
			? m.page_edit_parts_hint()
			: undefined
		: step === 'pages'
			? `${pageCount} · ${partCount}`
			: m.page_edit_parts_hint()}
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
	disabled={nothing || adding || (step === 'parts' && merging && replacing === null)}
	action={submit}
	top={step === 'pages' ? tools : undefined}
	bottom={step === 'pages' && phone.current ? phoneBottom : undefined}
	footNote={step === 'pages' ? m.page_edit_keys() : undefined}
>
	{#if step === 'pages'}
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
						mark={markFor(page.source)}
						name={nameFor(page.source, index + 1)}
						chosen={chosen.has(page.key)}
						ghost={drag?.keys.has(page.key) ?? false}
						tabindex={page.key === stop ? 0 : -1}
						onchoose={(range) => choose(page.key, range)}
						onview={() => showPage(index)}
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
	{:else}
		{#if merging}
			<Field.Field class="max-w-md">
				<Field.Label for="merge-target">{m.merge_target()}</Field.Label>
				<Select id="merge-target" bind:value={target} options={targets} />
				<Field.Description>{m.merge_target_hint()}</Field.Description>
			</Field.Field>
		{/if}
		{#each parts as part, index (index)}
			<Card.Root
				size="row"
				class={phone.current ? 'flex flex-col gap-3' : 'flex items-center gap-3'}
			>
				<div class="flex min-w-0 flex-1 items-center gap-3">
					<div class="flex shrink-0 gap-1" aria-hidden="true">
						{#each part.slice(0, 2) as page (page.key)}
							<PageImage src={page.image} class="max-h-14 max-w-11 rounded-sm border bg-card" />
						{/each}
					</div>
					<BeamTitle
						title={m.page_edit_part({ number: String(index + 1) })}
						onview={() => showPages(beamParts(), index, title)}
					/>
					<Badge variant="muted">{pagesOf(ranges[index])}</Badge>
				</div>
				<Segmented
					size="sm"
					equal={phone.current}
					class={phone.current ? 'w-full' : ''}
					label={m.page_edit_part({ number: String(index + 1) })}
					value={replacing === index ? 'replace' : 'new'}
					options={[
						{ value: 'replace', label: m.page_edit_version() },
						{ value: 'new', label: m.page_edit_new() }
					]}
					onchange={(value) => {
						if (value === 'replace') replacing = index;
						else if (replacing === index) replacing = null;
					}}
				/>
			</Card.Root>
		{/each}
		<Alert.Root variant="note">
			<Alert.Description>{outcome}</Alert.Description>
		</Alert.Root>
	{/if}
</EditorShell>

<DocumentChoice bind:open={picking} there={documents.map((item) => item.id)} onpick={addDocument} />
