// The web UI's packages: what lands in build/ stands in `dependencies`, the tools in
// `devDependencies` (.knowledge/process/dependencies.md). Renovate labels the updates by the
// group (`dependencies` or `dev-deps`), and `pnpm audit --prod` sees only the first.
import { describe, expect, it } from 'vitest';
import packageText from '../package.json?raw';
import appCss from '../src/app.css?raw';

const sources = import.meta.glob<string>(
	[
		'/src/**/*.{ts,js,svelte}',
		'!/src/**/*.test.ts',
		// Helpers of the tests only.
		'!/src/lib/testing/**',
		// Paraglide's half for a server; the app has none.
		'!/src/lib/paraglide/server.js'
	],
	{ query: '?raw', import: 'default', eager: true }
);
// The build's own plugins copy files of a package into build/ (`pdfjs/`, `swagger/`).
const plugins = import.meta.glob<string>('/vite-*.js', {
	query: '?raw',
	import: 'default',
	eager: true
});

const PACKAGE = /^(@[a-z0-9][\w.-]*\/)?[a-z0-9][\w.-]*$/;

/** The package a specifier names (`bits-ui`, `@lucide/svelte`); SvelteKit's modules (`$app/…`)
 * are its own; null for the app's own modules and for what is no package name (an example in a
 * comment). */
function packageOf(specifier: string): string | null {
	if (/^\$(app|env|service-worker)\b/.test(specifier)) return '@sveltejs/kit';
	if (/^[./#$]|^node:|^virtual:/.test(specifier)) return null;
	const [first, second] = specifier.split('?')[0].split('/');
	const name = first.startsWith('@') ? `${first}/${second}` : first;
	return PACKAGE.test(name) ? name : null;
}

/** The specifiers a module loads when it runs: no `import type`. */
function specifiers(source: string): string[] {
	const found: string[] = [];
	for (const [, kind, specifier] of source.matchAll(
		/^\s*(import\s+type\b|import|export)\b[^;'"]*?\bfrom\s+['"]([^'"]+)['"]/gms
	)) {
		if (!kind.startsWith('import type')) found.push(specifier);
	}
	for (const [, specifier] of source.matchAll(/^\s*import\s+['"]([^'"]+)['"]/gm)) {
		found.push(specifier);
	}
	for (const [, specifier] of source.matchAll(/\bimport\(\s*['"]([^'"]+)['"]\s*\)/g)) {
		found.push(specifier);
	}
	return found;
}

function shipped(): Set<string> {
	const names = new Set<string>();
	const add = (specifier: string) => {
		const name = packageOf(specifier);
		if (name) names.add(name);
	};
	for (const source of Object.values(sources)) specifiers(source).forEach(add);
	for (const [, specifier] of appCss.matchAll(/^@import\s+['"]([^'"]+)['"]/gm)) add(specifier);
	for (const source of Object.values(plugins)) {
		for (const [, name] of source.matchAll(/\bresolve\(\s*'([^']+)\/package\.json'\s*\)/g)) {
			add(name);
		}
	}
	return names;
}

const { dependencies = {}, devDependencies = {} } = JSON.parse(packageText) as Record<
	string,
	Record<string, string> | undefined
>;

describe('the groups of the packages', () => {
	it('finds what the app loads, its style sheet and the copied files', () => {
		const names = shipped();
		for (const name of ['svelte', '@sveltejs/kit', 'bits-ui', 'tailwindcss', 'swagger-ui-dist']) {
			expect(names, name).toContain(name);
		}
	});

	// Svelte, SvelteKit's client, bits-ui and others stood among the tools: Renovate labelled
	// their updates as development dependencies (WK-04).
	it('lists what lands in build/ in dependencies, and only that', () => {
		expect([...shipped()].sort()).toEqual(Object.keys(dependencies).sort());
	});

	it('lists every package once', () => {
		expect(Object.keys(dependencies).filter((name) => name in devDependencies)).toEqual([]);
	});
});
