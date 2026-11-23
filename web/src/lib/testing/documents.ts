/**
 * Builders for tests of documents and the inbox, and a fake of the API that answers by method
 * and path.
 */
import type { components } from '#lib/api/schema.ts';

type Document = components['schemas']['DocumentDetails'];
type Listed = components['schemas']['ListedDocument'];
type InboxItem = components['schemas']['InboxItemOut'];
type InboxTab = components['schemas']['InboxTab'];
type Summary = components['schemas']['InboxSummaryOut'];
type Processing = components['schemas']['Processing'];

export const OWNER = 'user-1';

/** Processing ended (`run` 1, every node done) or, with `running`, at the text recognition. */
export function processingOf(running = false): Processing {
	return {
		status: running ? 'processing' : 'completed',
		run: 1,
		vision: false,
		nodes: [
			{ node: 'receive', status: 'done', outcome: 'ok', started_at: null, finished_at: null },
			{
				node: 'ocr',
				status: running ? 'running' : 'done',
				outcome: running ? null : 'ok',
				started_at: null,
				finished_at: null
			}
		]
	} as Processing;
}

export function documentOf(changes: Partial<Document> = {}): Document {
	return {
		id: 'doc-1',
		title: 'Stromrechnung',
		original_filename: 'scan.pdf',
		media_type: 'application/pdf',
		channel: 'web',
		sha256: 'a'.repeat(64),
		uploaded_by: OWNER,
		space_id: 'space-1',
		access: 'edit',
		contact_id: null,
		document_type_id: null,
		topic_id: null,
		tag_ids: [],
		document_date: null,
		fields: {},
		lane: 'green',
		first_lane: null,
		page_count: 1,
		confirmed_at: null,
		processing: processingOf(changes.lane === null),
		created_at: '2026-10-18T08:00:00Z',
		updated_at: '2026-10-18T08:00:00Z',
		...changes
	};
}

export function listedOf(changes: Partial<Listed> = {}): Listed {
	return { ...documentOf(changes), in_inbox: false, ...changes };
}

const LANES: Record<InboxTab, Document['lane']> = {
	new: 'green',
	review: 'yellow',
	intervene: 'red',
	processing: null,
	done: 'green'
};

/** A document of the inbox under `tab`; done ones seen by the owner unless `done` says. */
export function inboxItem(
	tab: InboxTab,
	document: Partial<Document> = {},
	extra: Partial<InboxItem> = {}
): InboxItem {
	return {
		document: documentOf({ lane: LANES[tab], ...document }),
		tab,
		open: [],
		done: tab === 'done' ? { how: 'seen', at: '2026-10-18T09:30:00Z', by: OWNER } : null,
		...extra
	};
}

/** The summary of an inbox with these counts; open and the worst lane follow from them. */
export function summaryOf(counts: Partial<Summary> = {}): Summary {
	const base = { new: 0, review: 0, intervene: 0, processing: 0, done: 0, ...counts };
	return {
		...base,
		open: base.new + base.review + base.intervene + base.processing,
		worst_lane: base.intervene ? 'red' : base.review ? 'yellow' : base.new ? 'green' : null,
		...counts
	};
}

type Files = components['schemas']['DocumentFilesOut'];

/** The files of a document as received: one PDF, its first version, no archive copy. */
export function filesOf(overrides: Partial<Files> = {}): Files {
	return {
		added: '2026-10-15T08:00:00Z',
		modified: '2026-10-15T08:00:00Z',
		original_filename: 'scan.pdf',
		media_type: 'application/pdf',
		page_count: 1,
		original: { size: 12345, sha256: '0'.repeat(64), metadata: null },
		archive: null,
		versions: [
			{
				number: 1,
				current: true,
				original_filename: 'scan.pdf',
				media_type: 'application/pdf',
				kind: 'received',
				created_at: '2026-10-15T08:00:00Z',
				created_by: null,
				detail: {},
				origin: null
			}
		],
		...overrides
	};
}

type Lens = components['schemas']['LensOut'];

/** A filter of a lens that filters nothing. */
export const NO_LENS_FILTER: Lens['filter'] = {
	contact_ids: [],
	document_type_ids: [],
	contact_group_ids: [],
	document_type_group_ids: [],
	topic_ids: [],
	tag_ids: [],
	space_ids: [],
	field_id: null,
	document_date_from: null,
	document_date_to: null,
	document_period: null,
	facts: []
};

/** The lens `l1` "Zu bezahlen" in a grid, without words, sort or filter unless given. */
export function lensOf(
	parts: Omit<Partial<Lens>, 'filter'> & { filter?: Partial<Lens['filter']> } = {}
): Lens {
	const { filter, ...rest } = parts;
	return {
		id: 'l1',
		name: 'Zu bezahlen',
		position: 0,
		query: null,
		sort: null,
		sort_field_id: null,
		grouping: 'none',
		layout: 'grid',
		card_field_ids: [],
		due_field_id: null,
		created_at: '2026-10-20T10:00:00Z',
		updated_at: '2026-10-20T10:00:00Z',
		...rest,
		filter: { ...NO_LENS_FILTER, ...filter }
	};
}
