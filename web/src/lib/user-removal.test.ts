import { describe, expect, it } from 'vitest';
import type { components } from '#lib/api/schema.ts';
import {
	editorOptions,
	initialDecisions,
	moveTargets,
	removalBody,
	settled,
	type BlockingSpace
} from '#lib/user-removal.ts';

type Space = components['schemas']['SpaceOut'];

const ERIKA = 'erika-id';
const JOHN = 'john-id';
const GONE = 'gone-id';
const users = [
	{ id: ERIKA, username: 'erika', active: true },
	{ id: JOHN, username: 'john', display_name: 'John Doe', active: true },
	{ id: GONE, username: 'gone', active: false }
];

function space(id: string, name: string, personal_of: string | null = null): Space {
	return {
		id,
		name,
		personal_of,
		description: null,
		role: 'edit',
		members: [],
		created_at: '2026-10-22T00:00:00Z',
		version: 1
	} as unknown as Space;
}

const personal: BlockingSpace = {
	space_id: 'erikas',
	name: 'Personal',
	personal: true,
	documents: 3,
	choices: ['move_to']
};
const household: BlockingSpace = {
	space_id: 'household',
	name: 'Household',
	personal: false,
	documents: 1,
	choices: ['move_to', 'editor']
};
const empty: BlockingSpace = {
	space_id: 'empty',
	name: 'Empty',
	personal: false,
	documents: 0,
	choices: ['remove', 'editor']
};

describe('deleting a user who leaves spaces behind', () => {
	it('starts at the first choice and waits for every target', () => {
		const spaces = [personal, household, empty];
		const decisions = initialDecisions(spaces);
		expect(decisions).toEqual({
			erikas: { how: 'move_to', target: '' },
			household: { how: 'move_to', target: '' },
			empty: { how: 'remove', target: '' }
		});
		expect(settled(spaces, decisions)).toBe(false);
		decisions.erikas.target = 'johns';
		decisions.household = { how: 'editor', target: JOHN };
		expect(settled(spaces, decisions)).toBe(true);
		expect(removalBody(spaces, decisions)).toEqual({
			spaces: [
				{ space_id: 'erikas', remove: false, move_to: 'johns' },
				{ space_id: 'household', remove: false, editor: JOHN },
				{ space_id: 'empty', remove: true }
			]
		});
		expect(settled([personal], { erikas: { how: 'remove', target: '' } })).toBe(false);
	});

	it('moves only into spaces that stay, never to a deactivated user', () => {
		const spaces = [
			space('erikas', 'Personal', ERIKA),
			space('household', 'Household'),
			space('johns', 'Personal', JOHN),
			space('gones', 'Personal', GONE),
			space('archive', 'Archive')
		];
		const targets = moveTargets(spaces, users, ERIKA, [personal, household], 'admin-id');
		expect(targets.map((target) => target.value)).toEqual(['archive', 'johns']);
		expect(editorOptions(users, ERIKA)).toEqual([{ value: JOHN, label: 'John Doe (john)' }]);
	});
});
