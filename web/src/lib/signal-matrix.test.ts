import { describe, expect, it } from 'vitest';
import type { components } from '#lib/api/schema.ts';
import { m } from '#lib/paraglide/messages.js';
import { decidedBy, matrixOf, verdictOf } from './signal-matrix.ts';
import { lookupOf } from '#lib/testing/master-data.ts';
import { logEntry } from '#lib/testing/pipeline.ts';

type LogEntry = components['schemas']['LogEntry'];

const JOHN = 'u-john';
const ERIKA = 'u-erika';
const MINE = 's-mine';
const ERIKAS = 's-erika';
const MUSTERVEREIN = 'c-musterverein';
const BAKERY = 'c-bakery';
const PAYSLIP = 't-payslip';

const lookup = lookupOf({
	contacts: [
		{ id: MUSTERVEREIN, name: 'Jugendverein Muster e.V.' },
		{ id: BAKERY, name: 'Muster Bäckerei' }
	],
	documentTypes: [{ id: PAYSLIP, name: 'Lohnabrechnung' }],
	tags: [],
	fields: [],
	spaces: [
		{
			id: MINE,
			name: 'Personal',
			personal_of: JOHN,
			role: 'edit',
			members: [{ user_id: JOHN, role: 'edit', username: 'john', active: true }]
		}
	],
	users: [
		{ id: JOHN, username: 'john', role: 'user', personal_space_id: MINE },
		{
			id: ERIKA,
			username: 'erika',
			display_name: 'Jane Doe',
			role: 'user',
			personal_space_id: ERIKAS
		}
	]
});

const john = { id: JOHN, admin: false };

function verdict(fields: unknown[]): LogEntry {
	return logEntry('judge', 3, {
		outcome: 'uncertain',
		reason: 'space: suggests another space',
		confidence: 0.6,
		model_version: 'model',
		output: { fields },
		started_at: '2026-10-23T09:00:00Z'
	});
}

const contact = {
	field: 'contact',
	outcome: 'ok',
	value: BAKERY,
	candidates: [
		{
			value: BAKERY,
			label: 'Muster Bäckerei',
			contradicted: false,
			sources: [
				{ signal: 'signal_llm', names: true, score: 1, threshold: 0.9 },
				{ signal: 'signal_facts', names: true, identifiers: ['personnel_number'] }
			]
		},
		{
			value: MUSTERVEREIN,
			label: 'Jugendverein Muster e.V.',
			contradicted: false,
			sources: [
				{ signal: 'signal_classifier', names: false, score: 0.52, threshold: 0.8 },
				{ signal: 'signal_neighbours', names: true, votes: 4, of: 5, similarity: 0.91 }
			]
		}
	]
};

const type = {
	field: 'document_type',
	outcome: 'ok',
	value: PAYSLIP,
	candidates: [
		{
			value: PAYSLIP,
			label: 'Lohnabrechnung',
			contradicted: false,
			sources: [
				{ signal: 'signal_llm', names: true },
				{ signal: 'signal_classifier', names: true, score: 0.91, threshold: 0.8 },
				{ signal: 'signal_neighbours', names: true, votes: 5, of: 5 }
			]
		}
	]
};

const space = {
	field: 'space',
	outcome: 'uncertain',
	suggestion: ERIKAS,
	candidates: [
		{
			value: ERIKAS,
			label: 'Jane Doe',
			contradicted: true,
			sources: [
				{ signal: 'signal_llm', names: true, recipient: true },
				{ signal: 'signal_facts', names: false, named_in_text: true }
			]
		},
		{
			value: MINE,
			label: 'Personal',
			contradicted: false,
			sources: [{ signal: 'signal_neighbours', names: true, votes: 4, of: 5 }]
		}
	]
};

const kinds = (row: { cells: { kind: string }[] }) => row.cells.map((cell) => cell.kind);

describe('matrixOf', () => {
	it('tells per property what each signal said about its value', () => {
		const rows = matrixOf(verdict([contact, type, space]), true, MINE, lookup, john);
		expect(rows.map((row) => [row.label, row.value, row.open])).toEqual([
			[m.field_contact(), 'Muster Bäckerei', false],
			[m.field_document_type(), 'Lohnabrechnung', false],
			[m.field_space(), m.run_suggestion({ choice: m.move_hand_over({ name: 'Jane Doe' }) }), true]
		]);
		// Model names it, classifier too unsure, neighbours name another without proof, the
		// identifier proves it.
		expect(kinds(rows[0])).toEqual(['names', 'silent', 'other', 'evidence']);
		expect(rows[0].cells[1].title).toContain('52');
		expect(rows[0].chip).toBe(m.matrix_chip_identifier());
		expect(kinds(rows[1])).toEqual(['names', 'names', 'names', 'silent']);
		expect(rows[1].chip).toBe(m.matrix_chip_signals({ count: '3' }));
		// The open space: the neighbours name the uploader's space against the suggestion.
		expect(kinds(rows[2])).toEqual(['names', 'silent', 'contradicts', 'evidence']);
		expect(rows[2].chip).toBe(m.matrix_chip_question());
	});

	it('leaves out what has no candidates, and asks no one in a past run', () => {
		const date = { field: 'document_date', outcome: 'ok', value: '2025-05-08' };
		const rows = matrixOf(verdict([date, space]), false, MINE, lookup, john);
		expect(rows.map((row) => row.field)).toEqual(['space']);
		expect(rows[0].chip).toBe(m.matrix_chip_unsure());
		expect(matrixOf(undefined, false, MINE, lookup, john)).toEqual([]);
	});

	it('counts text evidence for another value, and what speaks against a contact by its rule', () => {
		// The identifier proves the bakery, the model names MUSTERVEREIN: MUSTERVEREIN is contradicted. The
		// neighbours name MUSTERVEREIN too: they speak for MUSTERVEREIN, not against.
		const proven = {
			field: 'contact',
			outcome: 'uncertain',
			suggestion: MUSTERVEREIN,
			candidates: [
				{
					value: MUSTERVEREIN,
					label: 'Jugendverein Muster e.V.',
					contradicted: true,
					sources: [
						{ signal: 'signal_llm', names: true },
						{ signal: 'signal_neighbours', names: true, votes: 4, of: 5 }
					]
				},
				{
					value: BAKERY,
					label: 'Muster Bäckerei',
					contradicted: true,
					sources: [
						{ signal: 'signal_classifier', names: true, score: 0.9, threshold: 0.8 },
						{ signal: 'signal_facts', identifiers: ['personnel_number'] }
					]
				}
			]
		};
		const [row] = matrixOf(verdict([proven]), true, MINE, lookup, john);
		// The classifier names the bakery, which the text proves: against MUSTERVEREIN; the identifier
		// itself too.
		expect(kinds(row)).toEqual(['names', 'contradicts', 'names', 'contradicts']);
		// Without a proof of the bakery, the classifier naming it does not speak against MUSTERVEREIN
		// (contradicted by something else, here the model's recipient).
		const unproven = structuredClone(proven);
		unproven.candidates[1].sources = [
			{ signal: 'signal_classifier', names: true, score: 0.9, threshold: 0.8 }
		];
		const [other] = matrixOf(verdict([unproven]), true, MINE, lookup, john);
		expect(kinds(other)).toEqual(['names', 'other', 'names', 'silent']);
	});

	it('shows what a person decided after the verdict as decided by hand', () => {
		const decided = decidedBy(
			{
				...verdict([]),
				outcome: 'ok',
				model_version: 'person',
				output: { accepted: ['space'], entered: [], kept: [] }
			},
			{ contact: BAKERY, space: MINE }
		);
		expect([...decided]).toEqual([['space', MINE]]);
		const rows = matrixOf(verdict([space]), false, MINE, lookup, john, decided);
		expect(rows[0]).toMatchObject({ open: false, chip: m.matrix_chip_by_hand() });
		expect(rows[0].value).not.toContain('Erika');
	});
});

describe('verdictOf', () => {
	it("takes the latest verdict up to the run, not a person's confirmation", () => {
		const first = { ...verdict([]), run: 1 };
		const second = { ...verdict([]), run: 2 };
		const person = { ...verdict([]), run: 3, model_version: 'person' };
		expect(verdictOf([first, second, person], 3)).toBe(second);
		expect(verdictOf([first, second, person], 1)).toBe(first);
		expect(verdictOf([person], 3)).toBeUndefined();
	});
});
