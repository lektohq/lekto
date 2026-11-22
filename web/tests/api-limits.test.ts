/**
 * The limits of the forms are the API's: each constant against `openapi.json`, which a backend
 * test keeps current, so a changed limit in the backend fails here until the web UI follows.
 */
import { describe, expect, it } from 'vitest';
import openapi from '../openapi.json';
import { CODE_MAX } from '#lib/components/CodeDialog.svelte';
import { INBOX_PAGE_MAX } from '#lib/document-view.ts';
import { IDENTIFIER_VALUE_MAX } from '#lib/identifiers.ts';
import { LENS_LIMITS } from '#lib/lenses.ts';
import { LIMITS as MAILBOX_LIMITS } from '#lib/mailboxes.ts';
import { MAIL_VALUE_MAX, MAX_STEPS } from '#lib/mail-rules.ts';
import { MAX_HITS } from '#lib/bulk.ts';
import { LIST_PAGE_MAX, SEARCH_PAGE_MAX } from '#lib/list-places.ts';
import { MAX_MERGED } from '#lib/merge.ts';
import { MASTER_LIMITS } from '#lib/masterdata-api.ts';
import { PROFILE_LIMITS } from '#lib/profile.ts';
import { LIMITS } from '#lib/rules/model.ts';
import { TREE_LIMITS } from '#lib/rules/tree.ts';
import { MAX_SELECTED } from '#lib/selection.ts';
import { TIMEOUT } from '#lib/tasks.ts';
import { TOKEN_NAME_MAX } from '#lib/tokens.svelte.ts';
import { WEBHOOK_LIMITS } from '#lib/webhooks.ts';

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

/** A node with its reference resolved, of a union the branch that has `key` (a list's
 * `maxItems` beside a text: WT2-08), else the first that is not null. */
function resolve(node: Node, key?: string): Node {
	if (node.$ref !== undefined) return resolve(schemas[node.$ref.split('/').pop()!], key);
	if (node.anyOf !== undefined) {
		const branches = node.anyOf.map((each) => resolve(each));
		return (
			branches.find((each) => key !== undefined && key in each) ??
			branches.find((each) => each.type !== 'null')!
		);
	}
	return node;
}

/** `Schema.property.property[]`: `[]` steps into the items. A path that is gone throws, so a
 * rename shows here. */
function at(path: string, key?: string): Node {
	const [name, ...steps] = path.split('.');
	let node = schemas[name];
	if (node === undefined) throw new Error(`no schema ${name}`);
	for (const step of steps) {
		const items = step.endsWith('[]');
		const child = resolve(node).properties?.[items ? step.slice(0, -2) : step];
		if (child === undefined) throw new Error(`no ${step} in ${path}`);
		node = items ? resolve(child).items! : child;
	}
	return resolve(node, key);
}

/** A query parameter of `method path`. */
function param(path: string, method: 'get' | 'post', name: string): Node {
	const paths = (
		openapi as unknown as {
			paths: Record<string, Record<string, { parameters: { name: string; schema: Node }[] }>>;
		}
	).paths;
	const found = paths[path]?.[method]?.parameters.find((each) => each.name === name);
	if (found === undefined) throw new Error(`no ${name} at ${method} ${path}`);
	return resolve(found.schema);
}

/** A part of the multipart body of `POST path`, as the JSON it carries. */
function formPart(path: string, name: string): Node {
	const paths = (
		openapi as unknown as {
			paths: Record<
				string,
				{
					post: {
						requestBody: {
							content: Record<string, { schema: { properties: Record<string, Node> } }>;
						};
					};
				}
			>;
		}
	).paths;
	const part = paths[path]?.post.requestBody.content['multipart/form-data'].schema.properties[name];
	if (part === undefined) throw new Error(`no ${name} in POST ${path}`);
	return resolve((part.contentSchema as Node | undefined) ?? part);
}

type Key = 'maxLength' | 'maxItems' | 'minimum' | 'maximum' | 'default';

const W = WEBHOOK_LIMITS;
const M = MASTER_LIMITS;
const P = PROFILE_LIMITS;

const PAIRS: [label: string, ours: number, path: string, key: Key][] = [
	['WEBHOOK_LIMITS.name', W.name, 'WebhookCreate.name', 'maxLength'],
	['WEBHOOK_LIMITS.name', W.name, 'WebhookPatch.name', 'maxLength'],
	['WEBHOOK_LIMITS.url', W.url, 'WebhookCreate.url', 'maxLength'],
	['WEBHOOK_LIMITS.body', W.body, 'WebhookCreate.body_template', 'maxLength'],
	['WEBHOOK_LIMITS.headers', W.headers, 'WebhookCreate.headers', 'maxItems'],
	['WEBHOOK_LIMITS.headerName', W.headerName, 'HeaderIn.name', 'maxLength'],
	['WEBHOOK_LIMITS.headerValue', W.headerValue, 'HeaderIn.value', 'maxLength'],
	['WEBHOOK_LIMITS.openTasks.min', W.openTasks.min, 'WebhookCreate.max_open_tasks', 'minimum'],
	['WEBHOOK_LIMITS.openTasks.max', W.openTasks.max, 'WebhookCreate.max_open_tasks', 'maximum'],
	[
		'WEBHOOK_LIMITS.openTasks.default',
		W.openTasks.default,
		'WebhookCreate.max_open_tasks',
		'default'
	],
	['TIMEOUT.min', TIMEOUT.min, 'AskWebhookAction.timeout_seconds', 'minimum'],
	['TIMEOUT.max', TIMEOUT.max, 'AskWebhookAction.timeout_seconds', 'maximum'],
	['TIMEOUT.default', TIMEOUT.default, 'AskWebhookAction.timeout_seconds', 'default'],
	['TIMEOUT.min', TIMEOUT.min, 'WebhookModelCallIn.timeout_seconds', 'minimum'],
	['TIMEOUT.max', TIMEOUT.max, 'WebhookModelCallIn.timeout_seconds', 'maximum'],
	['TIMEOUT.default', TIMEOUT.default, 'WebhookModelCallIn.timeout_seconds', 'default'],
	['LIMITS.stepName', LIMITS.stepName, 'AskWebhookAction.name', 'maxLength'],
	['LIMITS.name', LIMITS.name, 'RuleCreate.name', 'maxLength'],
	['LIMITS.name', LIMITS.name, 'MailRuleCreate.name', 'maxLength'],
	['LIMITS.priorityMin', LIMITS.priorityMin, 'RuleCreate.priority', 'minimum'],
	['LIMITS.priorityMax', LIMITS.priorityMax, 'RuleCreate.priority', 'maximum'],
	['LIMITS.actions', LIMITS.actions, 'RuleCreate.actions', 'maxItems'],
	['LIMITS.text', LIMITS.text, 'SetTitleAction.template', 'maxLength'],
	['LIMITS.text', LIMITS.text, 'ForceReviewAction.reason', 'maxLength'],
	['LIMITS.list', LIMITS.list, 'ConditionSchema.value', 'maxItems'],
	['LIMITS.list', LIMITS.list, 'AddTagsAction.tag_ids', 'maxItems'],
	['LIMITS.path', LIMITS.path, 'ConditionSchema.path', 'maxLength'],
	['MAIL_VALUE_MAX', MAIL_VALUE_MAX, 'MailConditionBody.value', 'maxLength'],
	[
		'TREE_LIMITS.conditions',
		TREE_LIMITS.conditions,
		'GroupItems_ConditionSchema_-Input',
		'maxItems'
	],
	['MAX_STEPS', MAX_STEPS, 'MailRuleCreate.after', 'maxItems'],
	['MAILBOX_LIMITS.name', MAILBOX_LIMITS.name, 'MailboxCreate.name', 'maxLength'],
	['MAILBOX_LIMITS.host', MAILBOX_LIMITS.host, 'MailboxCreate.host', 'maxLength'],
	['MAILBOX_LIMITS.username', MAILBOX_LIMITS.username, 'MailboxCreate.username', 'maxLength'],
	['MAILBOX_LIMITS.password', MAILBOX_LIMITS.password, 'MailboxCreate.password', 'maxLength'],
	['MAILBOX_LIMITS.folder', MAILBOX_LIMITS.folder, 'MailboxCreate.folders[]', 'maxLength'],
	['MAILBOX_LIMITS.folders', MAILBOX_LIMITS.folders, 'MailboxCreate.folders', 'maxItems'],
	['MAILBOX_LIMITS.folders', MAILBOX_LIMITS.folders, 'MailboxPatch.folders', 'maxItems'],
	...(['ContactCreate', 'DocumentTypeCreate', 'TagCreate', 'FieldCreate', 'SpaceCreate'].map(
		(schema) => ['MASTER_LIMITS.name', M.name, `${schema}.name`, 'maxLength']
	) as [string, number, string, Key][]),
	...(['DocumentTypeCreate', 'FieldCreate', 'SpaceCreate'].map((schema) => [
		'MASTER_LIMITS.description',
		M.description,
		`${schema}.description`,
		'maxLength'
	]) as [string, number, string, Key][]),
	['MASTER_LIMITS.alias', M.alias, 'ContactCreate.aliases[]', 'maxLength'],
	['MASTER_LIMITS.alias', M.alias, 'ContactPatch.aliases[]', 'maxLength'],
	['MASTER_LIMITS.aliases', M.aliases, 'ContactCreate.aliases', 'maxItems'],
	['MASTER_LIMITS.aliases', M.aliases, 'ContactPatch.aliases', 'maxItems'],
	['MASTER_LIMITS.titlePattern', M.titlePattern, 'DocumentTypeCreate.title_pattern', 'maxLength'],
	['MASTER_LIMITS.position.min', M.position.min, 'FieldCreate.position', 'minimum'],
	['MASTER_LIMITS.position.max', M.position.max, 'FieldCreate.position', 'maximum'],
	['PROFILE_LIMITS.username', P.username, 'UserCreate.username', 'maxLength'],
	['PROFILE_LIMITS.displayName', P.displayName, 'UserCreate.display_name', 'maxLength'],
	['PROFILE_LIMITS.displayName', P.displayName, 'ProfilePatch.display_name', 'maxLength'],
	['PROFILE_LIMITS.alias', P.alias, 'ProfilePatch.aliases[]', 'maxLength'],
	['PROFILE_LIMITS.aliases', P.aliases, 'ProfilePatch.aliases', 'maxItems'],
	...(['IdentifierIn', 'PersonIdentifierIn', 'ContactNumberIn'].map((schema) => [
		'IDENTIFIER_VALUE_MAX',
		IDENTIFIER_VALUE_MAX,
		`${schema}.value`,
		'maxLength'
	]) as [string, number, string, Key][]),
	['LENS_LIMITS.name', LENS_LIMITS.name, 'LensCreate.name', 'maxLength'],
	['LENS_LIMITS.cardFields', LENS_LIMITS.cardFields, 'LensCreate.card_field_ids', 'maxItems'],
	['TOKEN_NAME_MAX', TOKEN_NAME_MAX, 'TokenCreate.name', 'maxLength'],
	['CODE_MAX', CODE_MAX, 'CodeIn.code', 'maxLength']
	// Not in the OpenAPI document, held by the backend's code only: TREE_LIMITS.depth,
	// LIMITS.pattern, MAX_DOCUMENTS (lib/bulk.ts).
];

/** A field that is a number or a length of its own and no limit of the API (`#rrggbb`, an ISO
 * 4217 currency, a port, a sign-in code). This list may only shrink. */
const FORMATS = new Set([
	'/src/lib/components/ColorPicker.svelte',
	'/src/lib/components/FieldValueInput.svelte',
	'/src/lib/components/rules/ValueInput.svelte',
	'/src/lib/components/system/MailboxDialog.svelte',
	'/src/routes/login/+page.svelte'
]);

const components = import.meta.glob('/src/**/*.svelte', {
	query: '?raw',
	import: 'default',
	eager: true
}) as Record<string, string>;

describe('the limits of the forms', () => {
	it.each(PAIRS)('%s is the API’s (%s %s)', (_, ours, path, key) => {
		// A default stands at the property itself, before a nullable branch is resolved.
		expect(ours).toBe(at(path, key)[key]);
	});

	it('finds a limit in any branch of a union, not only the first', () => {
		// `ConditionSchema.value` is a text, a number, … or a list: its `maxItems` is the list's.
		expect(at('ConditionSchema.value', 'maxItems').maxItems).toBe(100);
		expect(at('ConditionSchema.value').type).toBe('string');
	});

	it('reads lists and searches in pages as large as the API takes, as far as it looks', () => {
		expect(LIST_PAGE_MAX).toBe(param('/api/v1/documents', 'get', 'limit').maximum);
		expect(SEARCH_PAGE_MAX).toBe(param('/api/v1/documents/search', 'post', 'limit').maximum);
		// A search by words reaches its hits up to this offset.
		expect(MAX_HITS).toBe(param('/api/v1/documents/search', 'post', 'offset').maximum);
	});

	it('merges as many documents as an edit takes', () => {
		expect(MAX_MERGED).toBe(formPart('/api/v1/documents/{id}/edit', 'documents').maxItems);
	});

	it('selects as many documents by id as the list takes', () => {
		expect(MAX_SELECTED).toBe(param('/api/v1/documents', 'get', 'ids').maxItems);
	});

	it('reads the inbox in pages as large as it takes', () => {
		expect(INBOX_PAGE_MAX).toBe(param('/api/v1/inbox', 'get', 'limit').maximum);
	});

	it('types no limit into a component: each comes from its constant', () => {
		const literal = /\b(?:maxlength|min|max)=\{-?\d/;
		const found = Object.entries(components)
			.filter(([path, source]) => !FORMATS.has(path) && literal.test(source))
			.map(
				([path, source]) =>
					`${path}: ${source
						.split('\n')
						.find((line) => literal.test(line))
						?.trim()}`
			);
		expect(found).toEqual([]);
	});

	it('gives the template editors no limit of their own', () => {
		const own = /maxlength = \d|maxlength \?\? \d/;
		const editors = {
			...components,
			...(import.meta.glob(
				['/src/lib/templates/*.ts', '/src/lib/testing/fake-template-editor.ts'],
				{ query: '?raw', import: 'default', eager: true }
			) as Record<string, string>)
		};
		const found = Object.entries(editors)
			.filter(([path, source]) => /\/templates?\/|template-editor/.test(path) && own.test(source))
			.map(([path]) => path);
		expect(found).toEqual([]);
	});
});
