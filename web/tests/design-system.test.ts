// The rules of web/DESIGN.md that a machine can check, over every component and page: tokens
// only (no arbitrary font sizes, radii, shadows or palette colours), one page title, one table,
// tooltips instead of native titles on buttons, dialog widths by their size, icon buttons
// through `IconButton`, one way to view a document (the Beam), toggle chips only where each
// toggles on its own, one order on the master data tabs, tooltips through `ui/tooltip`, a run's
// progress in the selection bar, fields in the API's order, short lines under fields, a document's
// pages through `DocumentPages`, a topic chosen through the tag picker, one height for fields,
// dates and times through `DateInput`, "Abbrechen" before the primary action, the owl only at its
// places. An exception needs its line in DESIGN.md ("Exceptions") and here; the lists of
// exceptions may only shrink.
import { describe, expect, it } from 'vitest';
import de from '../messages/de.json';
import en from '../messages/en.json';

const sources = import.meta.glob<string>('/src/**/*.svelte', {
	query: '?raw',
	import: 'default',
	eager: true
});

// Scripts too, for rules about what code does rather than markup.
const scripts = import.meta.glob<string>(
	['/src/**/*.ts', '!/src/**/*.test.ts', '!/src/lib/paraglide/**'],
	{
		query: '?raw',
		import: 'default',
		eager: true
	}
);

/** Files whose markup may break a rule, by rule, each for the reason DESIGN.md gives. */
const EXCEPTIONS = {
	// The wordmark's size on the sign-in and the error page: the logo scales with its font size.
	fontSize: new Set(['/src/routes/login/+page.svelte', '/src/routes/+error.svelte']),
	// The sign-in page's fields: larger, alone on the page, the code to type in large digits.
	fieldHeight: new Set(['/src/routes/login/+page.svelte']),
	// Frames whose rows or buttons pad themselves top and bottom; the frame pads the sides.
	flushPadding: new Set([
		'/src/lib/components/FilterSection.svelte',
		'/src/lib/components/Lenses.svelte',
		'/src/lib/components/SelectionBar.svelte',
		'/src/lib/components/system/MaintenanceTab.svelte'
	]),
	// Paper, logos and the QR code are drawn for white; the overlays of shadcn's dialogs.
	palette: new Set([
		'/src/lib/components/document/CodeThumb.svelte',
		'/src/lib/components/DocumentThumb.svelte',
		'/src/lib/components/PageViewer.svelte',
		'/src/lib/components/TotpCard.svelte',
		'/src/lib/components/ContactAvatar.svelte',
		'/src/lib/components/ui/alert-dialog/alert-dialog-overlay.svelte',
		'/src/lib/components/ui/dialog/dialog-overlay.svelte',
		'/src/lib/components/ui/sheet/sheet-overlay.svelte'
	])
} as const;

/** Where the eye (`scan-eye`) stands, which only ever means "show in the Beam" (DESIGN.md, "Beam"):
 * before a document's title and before "Woher gelernt?". */
const EYE = new Set([
	'/src/lib/components/BeamTitle.svelte',
	'/src/lib/components/IdentifiersEditor.svelte'
]);

/** Where a link to one document stands (DESIGN.md, "Beam"): the cards and rows of the lists and
 * the stream's chips build it for `DocumentLink`; "Dokument öffnen" of the Beam; the mark "Im
 * Eingang" and the paging through the inbox, which are navigation. Elsewhere a document's title
 * opens the Beam (`BeamTitle`). */
const DOCUMENT_LINKS = new Set([
	'/src/lib/components/DocumentCard.svelte',
	'/src/lib/components/DocumentRow.svelte',
	'/src/lib/components/InboxRow.svelte',
	'/src/lib/components/documents/StreamView.svelte',
	'/src/lib/components/Beam.svelte',
	'/src/lib/components/InboxMark.svelte',
	'/src/lib/components/document/DocumentPlace.svelte',
	'/src/routes/(app)/documents/[id]/+page.svelte'
]);
const DOCUMENT_LINK = /documentHref\(|inboxDocument\(|BASE\}\/documents\/(?:\{|\$\{)/;

/** Where a chip toggles on its own (DESIGN.md, "Tabs and switches"): several at once or none, the
 * channels of the automation, the quick picks of a period and the values of a filter; the style
 * guide shows it. One of a few, always one, is `Segmented`. */
const TOGGLE_CHIPS = new Set([
	'/src/lib/components/FacetChips.svelte',
	'/src/lib/components/PeriodFacet.svelte',
	'/src/lib/components/system/AutomationTab.svelte',
	'/src/routes/(app)/dev/components/+page.svelte'
]);

/** Where the owl stands (DESIGN.md, "Logo and owl"): the sign-in, the page that does not exist,
 * and through `EmptyNote` the inbox with nothing waiting and the documents before the first one;
 * the style guide shows it. */
const MASCOT = new Set([
	'/src/lib/components/EmptyNote.svelte',
	'/src/routes/login/+page.svelte',
	'/src/routes/+error.svelte'
]);
const MASCOT_NOTES = new Set([
	'/src/routes/(app)/inbox/+page.svelte',
	'/src/routes/(app)/documents/+page.svelte',
	'/src/routes/(app)/dev/components/+page.svelte'
]);

/** The narrow filter panel and the lens editor beside it: their fields are 36 pixels high. */
const PANELS = new Set([
	'/src/lib/components/FilterPanel.svelte',
	'/src/lib/components/FactFilter.svelte',
	'/src/lib/components/LensEditor.svelte'
]);

/** Where a `Progress` stands (DESIGN.md, "Choosing many"): the selection bars of a run on many, and
 * the summary of an upload. */
const PROGRESS = new Set([
	'/src/lib/components/DocumentsBulkBar.svelte',
	'/src/lib/components/rules/RuleApplyBar.svelte',
	'/src/lib/components/UploadSummary.svelte'
]);
/** Popovers drawn outside `ui/`: they use the component's shadow (DESIGN.md, "Radius, borders,
 * shadows"). This list may only shrink. */
const POPOVERS = new Set([
	'/src/lib/components/InfoTip.svelte',
	'/src/lib/components/DateInput.svelte',
	'/src/lib/components/Select.svelte'
]);

/** The shadows DESIGN.md names besides them: the chosen option's pill of `Segmented`, the paper
 * of the viewer's pages, "Nach oben" floating over the content (Tobi, 09.11.2026). */
const SHADOWS = new Set([
	'/src/lib/components/Segmented.svelte',
	'/src/lib/components/PageViewer.svelte',
	'/src/lib/components/pages/PageTile.svelte',
	'/src/lib/components/ToTop.svelte'
]);

/** Where a native title names the options of a picker (DESIGN.md, "Help and tooltips"): the
 * swatches of the colours, the icons, the months of a period, the paths of tags on the filter's
 * chips (a `TagChip` toggle). This list may only shrink. */
const PICKER_TITLES = new Set([
	'/src/lib/components/ColorPicker.svelte',
	'/src/lib/components/IconPickerPanel.svelte',
	'/src/lib/components/PeriodFacet.svelte',
	'/src/lib/components/TagChip.svelte'
]);

/** The master data tabs and what each shows below its search (DESIGN.md, "Master data tabs"). */
const MASTER_PAGE = '/src/routes/(app)/admin/master-data/+page.svelte';
const MASTER_PANELS = ['MasterDataList', 'TagsPanel', 'FieldsPanel', 'IdentifiersPanel'];

const PALETTE =
	/\b(?:text|bg|border|ring|fill|stroke|outline|decoration|from|to|via)-(?:white|black|slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)(?:-\d{2,3})?\b/;

/** The files that break a rule: each with the first offending line. */
function offenders(test: (source: string, path: string) => string | null): string[] {
	const found: string[] = [];
	for (const [path, source] of Object.entries(sources)) {
		const hit = test(source, path);
		if (hit !== null) found.push(`${path}: ${hit.trim().slice(0, 120)}`);
	}
	return found;
}

/** The first line of `source` that matches `pattern`, or null. */
function line(source: string, pattern: RegExp): string | null {
	return source.split('\n').find((text) => pattern.test(text)) ?? null;
}

/** The opening tags of `name` (`<Button ...>`, across lines). */
function tags(source: string, name: string): string[] {
	const found: string[] = [];
	const pattern = new RegExp(`<${name.replace('.', '\\.')}\\b`, 'g');
	for (const match of source.matchAll(pattern)) {
		let depth = 0;
		let end = match.index + match[0].length;
		for (; end < source.length; end++) {
			const char = source[end];
			if (char === '{') depth++;
			else if (char === '}') depth--;
			else if (char === '>' && depth === 0) break;
		}
		found.push(source.slice(match.index, end + 1));
	}
	return found;
}

/** The bodies of the snippets named `name` in `source`, the snippets inside them included. */
function snippets(source: string, name: string): string[] {
	const found: string[] = [];
	const start = `{#snippet ${name}(`;
	for (let at = source.indexOf(start); at !== -1; at = source.indexOf(start, at + 1)) {
		let depth = 0;
		const tokens = /\{#snippet\b|\{\/snippet\}/g;
		tokens.lastIndex = at;
		for (let token = tokens.exec(source); token; token = tokens.exec(source)) {
			depth += token[0] === '{/snippet}' ? -1 : 1;
			if (depth === 0) {
				found.push(source.slice(at, token.index));
				break;
			}
		}
	}
	return found;
}

describe('the design system (web/DESIGN.md)', () => {
	it('takes font sizes from the type scale only', () => {
		// Neither an arbitrary size nor a step of Tailwind's beyond the scale (`text-xl` and up).
		const outside = /\btext-(?:\[\d[\d.]*(?:px|rem|em)\]|xl|[2-9]xl)\b/;
		expect(
			offenders((source, path) => (EXCEPTIONS.fontSize.has(path) ? null : line(source, outside)))
		).toEqual([]);
	});

	it('takes radii from the tokens only', () => {
		expect(offenders((source) => line(source, /\brounded-(?:3xl|4xl|\[)/))).toEqual([]);
	});

	it('takes shadows from the tokens only, and the few DESIGN.md names', () => {
		expect(offenders((source) => line(source, /\bshadow-\[/))).toEqual([]);
		expect(
			offenders((source, path) =>
				path.includes('/components/ui/') || POPOVERS.has(path) || SHADOWS.has(path)
					? null
					: line(source, /\bshadow-(?:xs|sm|md|lg|xl|2xl)\b/)
			)
		).toEqual([]);
	});

	it('moves only where motion is wanted: spins, pulses and turns are motion-safe', () => {
		// DESIGN.md, "Motion"; the shadcn primitives in ui/ too.
		const spins = /(?<![\w:-])animate-(?:spin|pulse|ping|bounce)\b/;
		// A turn may instead be stopped for reduced motion in the same string.
		const turns = /(?<![\w:-])transition-transform\b(?![^'"\n]*motion-reduce:transition-none)/;
		const found = offenders((source) => line(source, spins) ?? line(source, turns));
		for (const [path, source] of Object.entries(scripts)) {
			const hit = line(source, spins) ?? line(source, turns);
			if (hit !== null) found.push(`${path}: ${hit.trim().slice(0, 120)}`);
		}
		expect(found).toEqual([]);
	});

	it('sticks things only below the header, at its offsets', () => {
		// DESIGN.md, "Sticky heads": right below it, on the line of the tools, with room, or
		// where the page says for the title of a group; the header itself at the top.
		const offsets = new Set(['16', '18', '20', '(--group-top)']);
		const sticky = /\bsticky\b[^'"`\n]*?(?<![\w-])top-([\w()-]+)/g;
		expect(
			offenders((source, path) => {
				for (const match of source.matchAll(sticky)) {
					const header = match[1] === '0' && path === '/src/lib/components/AppShell.svelte';
					if (!header && !offsets.has(match[1])) return match[0];
				}
				return null;
			})
		).toEqual([]);
	});

	it('gives every action of a selection bar its icon', () => {
		// DESIGN.md, "Choosing many": the actions are tools, each with its icon before its word.
		const icon = /<[A-Z]\w*\b[^>]*aria-hidden="true"/;
		const controls = /<Button\b[\s\S]*?<\/Button>|<a\b[^>]*buttonVariants[\s\S]*?<\/a>/g;
		expect(
			offenders((source) => {
				if (!source.includes('<SelectionBar')) return null;
				for (const name of ['actions', 'trail', 'pageActions']) {
					for (const body of snippets(source, name)) {
						const bare = (body.match(controls) ?? []).find((control) => !icon.test(control));
						if (bare) return bare.split('\n')[0];
					}
				}
				return null;
			})
		).toEqual([]);
	});

	it('takes colours from the tokens, not from the palette of Tailwind', () => {
		expect(
			offenders((source, path) => (EXCEPTIONS.palette.has(path) ? null : line(source, PALETTE)))
		).toEqual([]);
	});

	it('has one page title: <h1> only in PageTitle', () => {
		expect(
			offenders((source, path) =>
				path.endsWith('/page/PageTitle.svelte') ? null : line(source, /(?<!`)<h1[\s>]/)
			)
		).toEqual([]);
	});

	it('draws every table with ui/table', () => {
		expect(
			offenders((source, path) =>
				path.includes('/components/ui/table/') ? null : line(source, /<table[\s>]/)
			)
		).toEqual([]);
	});

	it('names buttons by tooltips, not by native titles', () => {
		expect(
			offenders((source, path) => {
				const names = ['Button', 'IconButton', 'DropdownMenu.Trigger'];
				// `tags` tells the case apart: `button` is the raw element, not `Button`.
				if (!PICKER_TITLES.has(path)) names.push('button');
				const tagged = names.flatMap((name) => tags(source, name));
				return tagged.find((tag) => /\stitle=/.test(tag)) ?? null;
			})
		).toEqual([]);
	});

	it('sizes dialogs by their size, not by a width of their own', () => {
		expect(
			offenders((source) => {
				const tagged = ['Dialog.Content', 'AlertDialog.Content', 'FormDialog'].flatMap((name) =>
					tags(source, name)
				);
				return tagged.find((tag) => /\bmax-w-(?!none\b)/.test(tag)) ?? null;
			})
		).toEqual([]);
	});

	it('shows the eye only where a click shows a document in the Beam', () => {
		expect(
			offenders((source, path) => (EYE.has(path) ? null : line(source, /icons\/scan-eye['"]/)))
		).toEqual([]);
	});

	it('opens a document directly only from a card of a list or from the Beam', () => {
		expect(
			offenders((source, path) => (DOCUMENT_LINKS.has(path) ? null : line(source, DOCUMENT_LINK)))
		).toEqual([]);
	});

	it('toggles chips on their own only where several or none may be chosen', () => {
		expect(
			offenders((source, path) =>
				TOGGLE_CHIPS.has(path)
					? null
					: ([...tags(source, 'Chip'), ...tags(source, 'TagChip')].find((tag) =>
							/\spressed\b/.test(tag)
						) ?? null)
			)
		).toEqual([]);
	});

	it('shows every master data tab as tabs, search, its filter row and its list', () => {
		const page = sources[MASTER_PAGE];
		const at = (name: string) => page.indexOf(`<${name}`);
		expect(at('TabBar')).toBeGreaterThan(-1);
		expect(at('SearchField')).toBeGreaterThan(at('TabBar'));
		for (const panel of MASTER_PANELS) expect(at(panel)).toBeGreaterThan(at('SearchField'));
		// A panel starts with its filter row or its list: no text between the search and them.
		expect(
			MASTER_PANELS.flatMap((panel) => {
				const path = `/src/lib/components/${panel}.svelte`;
				const markup = sources[path].split('</script>').at(-1)!;
				const list = Math.min(
					...['<PanelState', '<Card.Root', '<Table.Root'].map((tag) => {
						const index = markup.indexOf(tag);
						return index === -1 ? Infinity : index;
					})
				);
				const text = markup.search(/<p[\s>]/);
				return text !== -1 && text < list ? [path] : [];
			})
		).toEqual([]);
	});

	it('builds tooltips with ui/tooltip, which shows one at a time and none on a returned focus', () => {
		expect(
			offenders((source, path) =>
				path.startsWith('/src/lib/components/ui/tooltip/')
					? null
					: line(source, /\bTooltip\b[^;]*from 'bits-ui'/)
			)
		).toEqual([]);
	});

	it('draws icon buttons with IconButton (a label, a tooltip, no round shape)', () => {
		expect(
			offenders((source, path) => {
				if (path.includes('/components/ui/') || path.endsWith('/IconButton.svelte')) return null;
				// Also a trigger or link drawn by `buttonVariants` with an icon size.
				return (
					tags(source, 'Button').find((tag) => /size="icon/.test(tag)) ??
					line(source, /buttonVariants\(\{[^}]*\bsize:[^,}]*'icon/)
				);
			})
		).toEqual([]);
	});

	it('keeps fields in the order the API lists them, never sorts them again', () => {
		const sorted = /fields?\w*\]?\)?\??\.(?:sort|toSorted)\(/i;
		const found = offenders((source) => line(source, sorted));
		for (const [path, source] of Object.entries(scripts)) {
			const hit = line(source, sorted);
			if (hit !== null) found.push(`${path}: ${hit.trim().slice(0, 120)}`);
		}
		expect(found).toEqual([]);
	});

	it('gives the Beam no shadow, which Safari paints black at another zoom', () => {
		const beam = sources['/src/lib/components/Beam.svelte'];
		// Its attributes hold arrow functions (`=>`): up to its own class, not to the first `>`.
		expect(beam).toMatch(/<Sheet\.Content\b[\s\S]*?\sclass="[^"]*\bshadow-none\b/);
	});

	it('searches in SearchField only, as high as every field', () => {
		// The header, the documents page, pickers and lists alike (DESIGN.md, "Fields"): one look,
		// one height, the text size that keeps iOS from zooming.
		expect(
			offenders((source, path) =>
				!path.endsWith('/SearchField.svelte') && /\stype="search"/.test(source)
					? 'type="search"'
					: null
			)
		).toEqual([]);
		const field = sources['/src/lib/components/SearchField.svelte'];
		expect(field).toMatch(/size === 'sm' \? 'h-9\b[^']*' : cn\(FIELD_HEIGHT\b/);
		expect(field).toMatch(/\btext-base\b[^"]*\bsm:text-sm\b/);
	});

	it('keeps a label with help as high as one without', () => {
		const hint = sources['/src/lib/components/InfoHint.svelte'];
		expect(hint).toMatch(/<span class="-my-1 flex">\s*<InfoTip\b[^>]*size="sm"/);
	});

	it('keeps the line under a field short; what explains goes into the HintLabel', () => {
		const own = (text: string) => text.replace(/\{[^}]*\}/g, '').trim().length;
		const found = offenders((source) => {
			for (const match of source.matchAll(/<Field\.Description\b[^>]*>\s*([^<]*)/g)) {
				const key = /^\{m\.(\w+)\(/.exec(match[1])?.[1];
				if (key === undefined) return `${match[0]} (not a message)`;
				const texts = [de, en].map((messages) => (messages as Record<string, string>)[key]);
				if (texts.some((text) => own(text) > 60)) return `${key} (over 60 characters)`;
			}
			return null;
		});
		expect(found).toEqual([]);
	});

	it("shows a document's pages one way, in the document view and the Beam alike", () => {
		const viewers = /<(PdfViewer|PageImages)\b/;
		expect(
			offenders((source, path) =>
				path.endsWith('/DocumentPages.svelte') ? null : line(source, viewers)
			)
		).toEqual([]);
	});

	it('chooses a topic as a value one way, the tag picker with one choice', () => {
		expect(
			offenders((source) => {
				for (const [element] of source.matchAll(
					/<(?:TagPicker|SearchSelect|Select)\b[\s\S]*?\/>/g
				)) {
					// A select of anything about topics: its label, its options or the variables
					// that hold them name the topic.
					const topic = element.startsWith('<TagPicker')
						? /scope="topic"/.test(element)
						: /topic/i.test(element);
					const one = element.startsWith('<TagPicker') && /\bsingle\b/.test(element);
					// The topics a contact enables are several, chosen in the master data; a topic's
					// place in its tree is chosen as every tag's.
					const several = /title=\{m\.master_topics\(\)\}/.test(element);
					const parent = /bind:value=\{parentId\}/.test(element);
					if (topic && !one && !several && !parent) return element.split('\n')[0];
				}
				return null;
			})
		).toEqual([]);
	});

	it('keeps every field at one height, lower only in the narrow filter panel', () => {
		const field = /<(?:Select|Input|SearchSelect|DateInput|Textarea)\b[\s\S]*?\/>/g;
		// `class="h-9"` and `class={cn('h-9 …')}` alike.
		const height = (element: string) => /\sclass=(?:"[^"]*|\{[^}]*)\b(h-\d+)\b/.exec(element)?.[1];
		expect(
			offenders((source, path) => {
				if (EXCEPTIONS.fieldHeight.has(path) || path.includes('/components/ui/')) return null;
				// A raw field with a type of its own; a file, a search or a hidden one is no field of
				// a form, and the draft of ChipInput (no type) is a chip.
				const raw = tags(source, 'input').filter((tag) =>
					/\stype="(?!file|search|hidden)/.test(tag)
				);
				// A `SearchField` may hold an `end`, so only its own tag counts.
				const searches = tags(source, 'SearchField');
				for (const element of [
					...[...source.matchAll(field)].map(([match]) => match),
					...searches,
					...raw
				]) {
					const found = height(element);
					// A raw field takes the one height by hand; a component field has it already.
					const one = found === 'h-11' && element.startsWith('<input');
					if (found !== undefined && !one && !(found === 'h-9' && PANELS.has(path)))
						return `${element.split('\n')[0]} (${found})`;
				}
				return null;
			})
		).toEqual([]);
	});

	it('draws a box of tone only as an Alert', () => {
		// A hint with a tone, its radius and its padding: `ui/alert` (DESIGN.md, "Alerts").
		const classes = /\sclass=(?:"[^"]*"|\{[^}]*\})/g;
		const tone = /\bbg-(?:lane-yellow|lane-red|note)\b/;
		const box = (value: string) =>
			/\brounded-(?:lg|xl|2xl)\b/.test(value) && /\bpx-\d/.test(value) && /\bpy-\d/.test(value);
		expect(
			offenders((source, path) => {
				// The search check's figures are tiles in the lanes' tones, no hints.
				if (path.includes('/components/ui/') || path.endsWith('/system/SearchTab.svelte'))
					return null;
				return (
					[...source.matchAll(classes)]
						.map(([found]) => found)
						.find((found) => tone.test(found) && box(found)) ?? null
				);
			})
		).toEqual([]);
	});

	it('says that nothing is there only with EmptyNote', () => {
		// A dashed box of muted words (DESIGN.md, "States"); `size="sm"` inside a dialog.
		const classes = /\sclass=(?:"[^"]*"|\{[^}]*\})/g;
		const empty = (value: string) =>
			/\bborder-dashed\b/.test(value) &&
			/\brounded-(?:xl|2xl)\b/.test(value) &&
			/\btext-muted-foreground\b/.test(value);
		expect(
			offenders((source, path) =>
				path.endsWith('/EmptyNote.svelte')
					? null
					: ([...source.matchAll(classes)].map(([found]) => found).find(empty) ?? null)
			)
		).toEqual([]);
	});

	it('draws a card of a choice only as ChoiceCard', () => {
		// A radio alone is the start of a card (DESIGN.md, "Checkboxes, radios, switches"): one
		// look for chosen, a border and the panel, no ring.
		expect(
			offenders((source, path) =>
				path.includes('/components/ui/') || path.endsWith('/ChoiceCard.svelte')
					? null
					: (tags(source, 'ChoiceBox').find((tag) => /\stype="radio"/.test(tag)) ?? null)
			)
		).toEqual([]);
	});

	it('draws a chip only as Chip or TagChip', () => {
		// A pill of 24 or 32 pixels as a link or a label (DESIGN.md, "Chips").
		const pill = (tag: string) =>
			/\brounded-full\b/.test(tag) && /\bh-(?:6|8)\b/.test(tag) && /\bpx-(?:2|3)\b/.test(tag);
		expect(
			offenders((source, path) =>
				path.includes('/components/ui/') || /\/(?:Tag)?Chip\.svelte$/.test(path)
					? null
					: ([...tags(source, 'a'), ...tags(source, 'span')].find(pill) ?? null)
			)
		).toEqual([]);
	});

	it('draws the bar of an editor on a phone once', () => {
		// "Abbrechen", the title, the submit (DESIGN.md, "Dialogs, sheets, editors").
		expect(
			offenders((source, path) =>
				path.endsWith('/PhoneEditorBar.svelte') ? null : line(source, /grid-cols-\[1fr_auto_1fr\]/)
			)
		).toEqual([]);
	});

	it('keeps the colours of the tags to the tags', () => {
		// A tag's colour says which tag it is (DESIGN.md, "Chips"): only `chipLook()` and the colour
		// picker name them; a mark of another kind is a `Badge`.
		expect(
			[...Object.entries(sources), ...Object.entries(scripts)]
				.filter(
					([path, source]) =>
						!/\/(?:colors\.ts|ColorPicker\.svelte)$/.test(path) && /\(--tag-/.test(source)
				)
				.map(([path]) => path)
		).toEqual([]);
	});

	it('sizes buttons by their size, never by a height of their own', () => {
		// `Button` takes a finger's 44 pixels on a phone by itself (DESIGN.md, "Buttons", "Touch
		// targets"); `min-h-*` is no height of its own.
		const own = /(?<![\w-])(?:max-sm:|sm:|md:|lg:|max-lg:)?(?:h|size)-\d/;
		expect(
			offenders((source, path) => {
				if (path.includes('/components/ui/') || path.endsWith('/IconButton.svelte')) return null;
				const tagged = ['Button', 'IconButton'].flatMap((name) => tags(source, name));
				return (
					tagged.find((tag) => {
						// `class={action}` or `class={cn(action, …)}`: a constant of the same file.
						const named = /\sclass=\{(?:cn\()?(\w+)/.exec(tag)?.[1];
						const constant =
							named && new RegExp(`(?:const|@const) ${named} =([^;}]*)`).exec(source)?.[1];
						const own_class = /\sclass=(?:"[^"]*"|\{[^}]*\})/.exec(tag)?.[0] ?? '';
						return own.test(own_class) || own.test(constant ?? '');
					}) ?? null
				);
			})
		).toEqual([]);
	});

	it('keeps the buttons in an alert in their variant, never in its tone', () => {
		// DESIGN.md, "Alerts": a button in an alert is a Button of its variants.
		const tone =
			/(?<![\w-])(?:hover:)?(?:bg|text)-(?:note|lane|primary|destructive|caution|warning)/;
		expect(
			offenders((source) => {
				for (const [, inside] of source.matchAll(/<Alert\.Root\b([\s\S]*?)<\/Alert\.Root>/g)) {
					const tinted = ['Button', 'IconButton']
						.flatMap((name) => tags(inside, name))
						.find((tag) => tone.test(/\sclass=(?:"[^"]*"|\{[^}]*\})/.exec(tag)?.[0] ?? ''));
					if (tinted) return tinted;
				}
				return null;
			})
		).toEqual([]);
	});

	it('takes dates and times through DateInput, never a field in the language of the browser', () => {
		// The stand-in of `DateInput` in the component tests (`lib/testing`) is no view.
		expect(
			offenders((source, path) =>
				path.startsWith('/src/lib/testing/')
					? null
					: line(source, /\btype=[^\n]*?["'](?:date|datetime-local|time|month|week)["']/)
			)
		).toEqual([]);
	});

	it('puts "Abbrechen" before the primary action, never after it', () => {
		// A footer reads "Abbrechen" (ghost), then the primary action (no variant): a primary
		// button directly followed by a ghost one turns the order round.
		expect(
			offenders((source) => {
				let from = 0;
				let previous: { tag: string; end: number } | null = null;
				for (const tag of tags(source, 'Button')) {
					const start = source.indexOf(tag, from);
					from = start + tag.length;
					if (
						previous &&
						/^\s*$/.test(source.slice(previous.end, start)) &&
						!/\bvariant=/.test(previous.tag) &&
						/\bvariant="ghost"/.test(tag)
					)
						return previous.tag.split('\n')[0];
					const close = /<\/Button\s*>/g;
					close.lastIndex = from;
					const closed = close.exec(source);
					previous = closed ? { tag, end: closed.index + closed[0].length } : null;
				}
				return null;
			})
		).toEqual([]);
	});

	it("shows a run's progress only in the selection bar of a run on many", () => {
		expect(
			offenders((source, path) =>
				PROGRESS.has(path) || path.includes('/components/ui/') ? null : line(source, /<Progress\b/)
			)
		).toEqual([]);
	});

	it('chooses a contact or a document type by searching, never from a plain Select', () => {
		const lists = /lookup\.(?:contacts|documentTypes)\b|\btypes\.map\(/;
		expect(
			offenders((source) => {
				for (const match of source.matchAll(/<Select\b[\s\S]*?\/>/g)) {
					if (lists.test(match[0])) return match[0].split('\n')[0];
				}
				return null;
			})
		).toEqual([]);
	});

	it('builds every rule, of documents and of mails, from one set of parts', () => {
		const own = (name: string) => `/src/lib/components/rules/${name}.svelte`;
		expect(
			offenders((source, path) =>
				path === own('ModeSelect') ? null : line(source, /m\.rule_mode_(?:all|any)\(/)
			)
		).toEqual([]);
		expect(
			offenders((source, path) =>
				path === own('RuleRow') ? null : line(source, /rounded-xl border bg-background p-3/)
			)
		).toEqual([]);
		expect(
			offenders((source, path) =>
				path === own('DryRunGroup') ? null : line(source, /m\.rule_group_(?:fold|unfold)\(/)
			)
		).toEqual([]); // One tree of conditions: the group and its reading are built once, for every kind.
		expect(
			offenders((source, path) =>
				path === own('ConditionGroup') ? null : line(source, /m\.rule_(?:negate|add_group)\(/)
			)
		).toEqual([]);
		expect(
			offenders((source, path) =>
				path.endsWith('/lib/rules/tree.ts')
					? null
					: line(source, /m\.rule_group_(?:not_)?(?:all|any)\(/)
			)
		).toEqual([]);
		// One switch and one way to switch, for rules, mailboxes and webhooks (`lib/rules/switch.ts`).
		expect(
			offenders((source, path) =>
				path === own('RuleSwitch') ? null : line(source, /m\.rule_switch_(?:on|off)\(/)
			)
		).toEqual([]);
		const switched = /m\.(?:rule|mailbox|webhook)_switched_(?:on|off)\(/;
		expect(
			[...Object.entries(sources), ...Object.entries(scripts)]
				.filter(([path, source]) => !path.endsWith('/lib/rules/switch.ts') && switched.test(source))
				.map(([path]) => path)
		).toEqual([]);
		for (const form of ['RuleBuilder', 'MailRuleForm']) {
			expect(sources[own(form)]).toMatch(/<ConditionGroup\b/);
		}
		for (const view of ['RuleView', 'MailRuleView']) {
			expect(sources[own(view)]).toMatch(/<ConditionTree\b/);
		}
	});

	it('spaces every page by gap-6 on every width, the document page by gap-4', () => {
		const frame = /^<div class="flex flex-col (gap-\d+)[^"]*"/m;
		expect(
			offenders((source, path) => {
				if (!path.startsWith('/src/routes/(app)/') || !path.endsWith('/+page.svelte')) return null;
				if (path === '/src/routes/(app)/dev/components/+page.svelte') return null;
				const gap = frame.exec(source)?.[1];
				if (gap === undefined) return null;
				const wanted = path === '/src/routes/(app)/documents/[id]/+page.svelte' ? 'gap-4' : 'gap-6';
				return gap === wanted ? null : `page frame ${gap}`;
			})
		).toEqual([]);
		expect(offenders((source) => line(source, /\bgap-4 sm:gap-6\b/))).toEqual([]);
	});

	it('formats in the language of the UI through lib/i18n.ts, never by a locale of its own', () => {
		// DESIGN.md, "Formats": dates, numbers and lists follow the UI language.
		const own =
			/resolvedOptions\(\)\.timeZone|documentElement\.lang\b(?!\s*=)|toLocaleDateString\(/;
		const allowed = new Set(['/src/lib/i18n.ts', '/src/lib/dates.ts']);
		expect(
			[...Object.entries(sources), ...Object.entries(scripts)]
				.filter(([path, source]) => !allowed.has(path) && own.test(source))
				.map(([path]) => path)
		).toEqual([]);
	});

	it('asks before a destructive action in a dialog of size md', () => {
		expect(
			offenders((source, path) =>
				path.includes('/components/ui/')
					? null
					: (tags(source, 'AlertDialog.Content').find((tag) => !/\ssize="md"/.test(tag)) ?? null)
			)
		).toEqual([]);
	});

	it('lists the appearances once', () => {
		const named = /m\.theme_(?:light|dark|system)\b/;
		expect(
			[...Object.entries(sources), ...Object.entries(scripts)]
				.filter(([path, source]) => path !== '/src/lib/theme.ts' && named.test(source))
				.map(([path]) => path)
		).toEqual([]);
	});

	it('draws a dot of alert only as AlertDot, with its words', () => {
		expect(
			offenders((source, path) =>
				path.endsWith('/AlertDot.svelte')
					? null
					: line(source, /size-\[7px\]|size-2 (?:shrink-0 )?rounded-full bg-destructive/)
			)
		).toEqual([]);
	});

	it("gives the date picker's arrows and days and the rows of choice lists a finger's size", () => {
		const picker = sources['/src/lib/components/DateInput.svelte'];
		for (const part of ['PrevButton', 'NextButton', 'Day'])
			expect(picker).toMatch(new RegExp(`<DatePicker\\.${part}\\b[^>]*\\bmax-sm:size-11\\b`));
		for (const list of ['MultiPicker', 'FacetList', 'FacetPicker'])
			expect(sources[`/src/lib/components/${list}.svelte`]).toMatch(
				/<label\b[^>]*\bmax-sm:min-h-11\b/
			);
	});

	it('gives a section title its help through SectionTitle tip', () => {
		expect(
			offenders((source, path) =>
				path.endsWith('/SectionTitle.svelte')
					? null
					: (/<\/SectionTitle>\s*<InfoTip\b/.exec(source)?.[0] ?? null)
			)
		).toEqual([]);
	});

	it('answers a fake API in tests through lib/testing/api.ts, never by a json of its own', () => {
		const tests = import.meta.glob<string>('/src/**/*.test.ts', {
			query: '?raw',
			import: 'default',
			eager: true
		});
		expect(
			Object.entries(tests)
				.filter(
					([, source]) =>
						/\bfunction json\(/.test(source) ||
						/Response\.json\(|new Response\(JSON\.stringify\(/.test(source)
				)
				.map(([path]) => path)
		).toEqual([]);
	});

	it('writes the API prefix once, beside the typed calls that need it as their type', () => {
		// `BASE_API` in `lib/api/base.ts`; `api.GET('/api/v1/…')` keeps the literal, which
		// openapi-fetch reads as the path's type.
		const found = [...Object.entries(sources), ...Object.entries(scripts)].flatMap(
			([path, source]) => {
				if (path === '/src/lib/api/base.ts' || path === '/src/lib/api/schema.ts') return [];
				const bare = source.replace(/\/\*[\s\S]*?\*\//g, '').replace(/<!--[\s\S]*?-->/g, '');
				return [...bare.matchAll(/['"`]\/api\/v1/g)]
					.filter((hit) => !/\.(?:GET|POST|PUT|PATCH|DELETE)\(\s*$/.test(bare.slice(0, hit.index)))
					.map(() => path);
			}
		);
		expect(found).toEqual([]);
	});

	it('links inside DESIGN.md only to headings it has', async () => {
		const design = (await import('../DESIGN.md?raw')).default;
		const slug = (heading: string) =>
			heading
				.toLowerCase()
				.replace(/[`*_]/g, '')
				.replace(/[^\p{L}\p{N} -]/gu, '')
				.replace(/ /g, '-');
		const anchors = new Set(
			[...design.matchAll(/^#{2,4} (.+)$/gm)].map((match) => slug(match[1].trim()))
		);
		const links = [...design.matchAll(/\]\(#([^)]+)\)/g)].map((match) => match[1]);
		expect(links.filter((link) => !anchors.has(link))).toEqual([]);
	});

	it('tells nothing only on hover: no native title on a field, a cell or a code', () => {
		// DESIGN.md, "Help and tooltips": information is never available only through hover.
		expect(
			offenders(
				(source) =>
					['Input', 'Table.Cell', 'code']
						.flatMap((name) => tags(source, name))
						.find((tag) => /\stitle=/.test(tag)) ?? null
			)
		).toEqual([]);
	});

	it('pads a card by its size, never a flush card by hand', () => {
		// DESIGN.md, "Spacing and layout": `Card` sizes only; `flush` is for a card whose rows pad.
		const padding = /(?<![\w-])(?:sm:|max-sm:)?p[xytrbl]?-\d/;
		expect(
			offenders((source, path) => {
				if (path.includes('/components/ui/') || EXCEPTIONS.flushPadding.has(path)) return null;
				const card = tags(source, 'Card.Root').find(
					(tag) =>
						/\ssize="flush"/.test(tag) &&
						padding.test(/\sclass=(?:"[^"]*"|\{[^}]*\})/.exec(tag)?.[0] ?? '')
				);
				if (card) return card;
				return (
					[...source.matchAll(/cardVariants\(\{\s*size:\s*'flush'\s*\}\),([^)]*)/g)].find((hit) =>
						padding.test(hit[1])
					)?.[0] ?? null
				);
			})
		).toEqual([]);
	});

	it('shows the owl only where a moment is rare: sign-in, not found, nothing waiting, no document', () => {
		expect(
			offenders((source, path) => (MASCOT.has(path) ? null : line(source, /<Mascot\b/)))
		).toEqual([]);
		expect(
			offenders((source, path) =>
				MASCOT_NOTES.has(path)
					? null
					: (tags(source, 'EmptyNote').find((tag) => /\bmascot\b/.test(tag)) ?? null)
			)
		).toEqual([]);
	});

	it('pages back and forth with a pair of arrows only through Stepper, Pagination and DateInput', () => {
		// A list's pages (`Pagination`) and a calendar's months (`DateInput`) have their own; every
		// "2 von 31" with previous and next is a `Stepper` ("Stepper").
		const own = new Set([
			'/src/lib/components/Stepper.svelte',
			'/src/lib/components/Pagination.svelte',
			'/src/lib/components/DateInput.svelte'
		]);
		expect(
			offenders((source, path) =>
				own.has(path) || !/icons\/chevron-right['"]/.test(source)
					? null
					: line(source, /icons\/chevron-left['"]/)
			)
		).toEqual([]);
	});
});
