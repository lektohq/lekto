/**
 * The Beam (web/DESIGN.md, "Beam"): a sheet from the right that shows a document's pages
 * without leaving the place, or the parts of an edit before they are stored. Its state lives in
 * the history entry (`page.state.beam`, ids only; `history-state.ts`): the back button closes it,
 * a reload brings it back, paging through its documents replaces the entry.
 */
import { page } from '$app/state';
import type { ShownPage } from '#lib/document-view.ts';
import type { IdentifierKind } from '#lib/identifiers.ts';
import { dropEntry, leaveEntry, pushEntry, replaceEntry } from '#lib/history-state.ts';

/** Where the places the Beam marks come from: an open identifier's detail
 * (`GET /identifiers/open/{kind}/{ref}`), the places of any identifier
 * (`GET /identifiers/places/{kind}/{ref}`); for each document, the place of a value (`fact`:
 * `GET /documents/{id}/places/{kind}/{ref}`, a relation's shared number), or the quotes of its
 * open fields (`review`: `GET /documents/{id}/review`, why it waits in the inbox), where a
 * rule's text conditions hit it (`rule`: `GET /rules/{id}/apply/hits/{document_id}`), or where
 * the words of a search stand (`search`: `POST /documents/{id}/search-places`, the words in the
 * body, here only in the history entry like the list's). */
export type BeamSource =
	| ValueSource
	| { kind: 'review' }
	| { kind: 'rule'; rule: string }
	| { kind: 'search'; words: string };

/** A source that names the places of a value of `identifier` by its reference. */
export interface ValueSource {
	kind: 'open' | 'places' | 'fact';
	identifier: IdentifierKind;
	ref: string;
}

export interface BeamState {
	/** The documents to page through, in order; none where it shows `parts`. */
	ids: string[];
	/** The parts of an edit it shows instead (`showPages`), by their key. */
	parts?: string;
	/** The one shown. */
	index: number;
	/** The page of a part to show first (from 1). */
	page?: number;
	/** The place it was opened from ("Dokumente"): the way back from the document names it. */
	from: string;
	/** Opened from the inbox: "Dokument öffnen" opens it there, with its neighbours. */
	inbox?: boolean;
	/** Opened from the document list: "Dokument öffnen" opens it with the list's neighbours. */
	list?: boolean;
	/** Where the marked places come from; without, the pages are shown from the first. */
	source?: BeamSource;
}

/** Open the Beam on `id`, paging through `ids` (each once); `from` names the place. */
export function openBeam(
	ids: readonly string[],
	id: string,
	from: string,
	options: { inbox?: boolean; list?: boolean; source?: BeamSource } = {}
): void {
	// eslint-disable-next-line svelte/prefer-svelte-reactivity
	const unique = [...new Set(ids)];
	const index = Math.max(0, unique.indexOf(id));
	pushEntry('beam', { ids: unique, index, from, ...options });
}

/** A part of an edit before it is stored, as the Beam shows it (`showPages`): its name, the
 * line below it, its pages as they are to be. */
export interface BeamPart {
	title: string;
	meta: string;
	pages: ShownPage[];
}

// The parts the Beam shows. The history entry names them by their key only: their images (an
// added file's among them) never go into it, and after a reload they are gone, as the edit is.
// The key counts up: `crypto.randomUUID` exists in a secure context only, not on an instance
// reached as http://10.0.0.5 (Tobi, 11.11.2026).
let shownParts: { key: string; parts: readonly BeamPart[] } | null = null;
let shownCount = 0;

/** Open the Beam on the parts of an edit before they are stored (web/DESIGN.md, "Beam"), at
 * part `index` and its page `page` (from 1); `from` names the place. */
export function showPages(parts: readonly BeamPart[], index: number, from: string, page = 1): void {
	shownCount += 1;
	const key = `parts-${shownCount}`;
	shownParts = { key, parts };
	pushEntry('beam', { ids: [], parts: key, index, page, from });
}

/** The parts the Beam's entry names by `key`, while they are kept (the last shown). */
export function partsOf(key: string): readonly BeamPart[] | null {
	return shownParts?.key === key ? shownParts.parts : null;
}

/** How many the open Beam pages through: documents, or the parts of an edit. */
export function beamCount(beam: BeamState): number {
	return beam.parts ? (partsOf(beam.parts)?.length ?? 0) : beam.ids.length;
}

/** Show the document (or part) at `index` of the open Beam, in the same history entry. */
export function beamTo(index: number): void {
	const beam = page.state.beam;
	if (!beam || index < 0 || index >= beamCount(beam)) return;
	replaceEntry('beam', { ...beam, index, page: undefined });
}

/** Close the Beam. */
export function closeBeam(): void {
	dropEntry('beam');
}

/** Leave the Beam for a document: whether the jump takes the Beam's history entry (the way back
 * then leads to the place without it). */
export function leaveBeam(): boolean {
	return leaveEntry('beam');
}
