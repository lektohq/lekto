// Every text a user reads comes from `messages/`: no words written straight into markup.
import { parse } from 'svelte/compiler';
import { describe, expect, it } from 'vitest';

const sources = import.meta.glob<string>('/src/**/*.svelte', {
	query: '?raw',
	import: 'default',
	eager: true
});

// The wordmark is a name, not a text.
const ALLOWED_FILES = new Set(['/src/lib/components/Logo.svelte']);
// Attributes whose value a user reads or hears.
const READ_ATTRIBUTES = new Set(['alt', 'title', 'placeholder', 'aria-label', 'aria-description']);

/** Text with letters, not only separators and numbers such as " · " or "42". */
function isText(value: string): boolean {
	return /\p{L}/u.test(value);
}

interface Node {
	type?: string;
	[key: string]: unknown;
}

function findings(source: string): string[] {
	const found: string[] = [];
	const visit = (value: unknown): void => {
		if (Array.isArray(value)) {
			value.forEach(visit);
			return;
		}
		if (!value || typeof value !== 'object') return;
		const node = value as Node;
		if (node.type === 'Text' && typeof node.data === 'string' && isText(node.data)) {
			found.push(node.data.trim());
		}
		if (node.type === 'Attribute') {
			// Values of other attributes (classes, types) are code.
			if (!READ_ATTRIBUTES.has(String(node.name))) return;
			const parts = Array.isArray(node.value) ? (node.value as Node[]) : [];
			for (const part of parts) {
				if (part.type === 'Text' && typeof part.data === 'string' && isText(part.data)) {
					found.push(`${String(node.name)}="${part.data}"`);
				}
			}
			return;
		}
		for (const [key, child] of Object.entries(node)) {
			// Scripts and styles are code, not markup.
			if (key === 'instance' || key === 'module' || key === 'css') continue;
			visit(child);
		}
	};
	visit(parse(source, { modern: true }).fragment);
	return found;
}

describe('markup', () => {
	it('finds the components', () => {
		expect(Object.keys(sources).length).toBeGreaterThan(20);
	});

	it.each(Object.keys(sources).filter((file) => !ALLOWED_FILES.has(file)))(
		'%s has no raw text',
		(file) => {
			expect(findings(sources[file])).toEqual([]);
		}
	);

	it('notices raw text', () => {
		expect(findings('<p>Hello</p>')).toEqual(['Hello']);
		expect(findings('<input placeholder="Name" />')).toEqual(['placeholder="Name"']);
		expect(findings('<p>{m.x()} · {m.app_name()}</p><p>42</p>')).toEqual([]);
	});
});

// Quotation marks belong to the language (`m.rule_quoted`, `quoted` in `lib/i18n.ts`): no „…“ or
// “…” in code, comments aside.
const code = import.meta.glob<string>(
	['/src/**/*.svelte', '/src/**/*.ts', '!/src/**/*.test.ts', '!/src/lib/paraglide/**'],
	{ query: '?raw', import: 'default', eager: true }
);

describe('quotation marks', () => {
	it('come from the messages, never from code', () => {
		const found = Object.entries(code).flatMap(([path, source]) => {
			const bare = source
				.replace(/\/\*[\s\S]*?\*\//g, '')
				.replace(/<!--[\s\S]*?-->/g, '')
				.replace(/(^|[^:'"`])\/\/.*$/gm, '$1');
			return /[„“”‚‘]/.test(bare) ? [path] : [];
		});
		expect(found).toEqual([]);
	});
});
