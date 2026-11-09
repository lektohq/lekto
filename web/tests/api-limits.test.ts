/**
 * The limits of the forms are the API's: each constant against `openapi.json`, which a backend
 * test keeps current, so a changed limit in the backend fails here until the web UI follows.
 */
import { describe, expect, it } from 'vitest';
import openapi from '../openapi.json';
import { MASTER_LIMITS } from '#lib/masterdata-api.ts';
import { PROFILE_LIMITS } from '#lib/profile.ts';

type Node = {
	$ref?: string;
	anyOf?: Node[];
	type?: string;
	properties?: Record<string, Node>;
	items?: Node;
	[key: string]: unknown;
};

const schemas = (openapi as unknown as { components: { schemas: Record<string, Node> } }).components
	.schemas;

/** A node with its reference and its nullable branch resolved. */
function resolve(node: Node): Node {
	if (node.$ref !== undefined) return resolve(schemas[node.$ref.split('/').pop()!]);
	if (node.anyOf !== undefined) return resolve(node.anyOf.find((each) => each.type !== 'null')!);
	return node;
}

/** `Schema.property.property[]`: `[]` steps into the items. A path that is gone throws, so a
 * rename shows here. */
function at(path: string): Node {
	const [name, ...steps] = path.split('.');
	let node = schemas[name];
	if (node === undefined) throw new Error(`no schema ${name}`);
	for (const step of steps) {
		const items = step.endsWith('[]');
		const child = resolve(node).properties?.[items ? step.slice(0, -2) : step];
		if (child === undefined) throw new Error(`no ${step} in ${path}`);
		node = items ? resolve(child).items! : child;
	}
	return resolve(node);
}

type Key = 'maxLength' | 'maxItems' | 'minimum' | 'maximum';

const PAIRS: [label: string, ours: number, path: string, key: Key][] = [
	['PROFILE_LIMITS.alias', PROFILE_LIMITS.alias, 'ProfilePatch.aliases[]', 'maxLength'],
	['PROFILE_LIMITS.aliases', PROFILE_LIMITS.aliases, 'ProfilePatch.aliases', 'maxItems'],
	['MASTER_LIMITS.alias', MASTER_LIMITS.alias, 'ContactCreate.aliases[]', 'maxLength'],
	['MASTER_LIMITS.alias', MASTER_LIMITS.alias, 'ContactPatch.aliases[]', 'maxLength'],
	['MASTER_LIMITS.aliases', MASTER_LIMITS.aliases, 'ContactCreate.aliases', 'maxItems'],
	['MASTER_LIMITS.aliases', MASTER_LIMITS.aliases, 'ContactPatch.aliases', 'maxItems']
];

describe('the limits of the forms', () => {
	it.each(PAIRS)('%s is the API’s (%s %s)', (_, ours, path, key) => {
		expect(ours).toBe(at(path)[key]);
	});
});
