import js from '@eslint/js';
import prettier from 'eslint-config-prettier';
import svelte from 'eslint-plugin-svelte';
import globals from 'globals';
import ts from 'typescript-eslint';

export default ts.config(
	{
		ignores: ['build/', '.svelte-kit/', 'src/lib/paraglide/', 'src/lib/api/schema.ts']
	},
	js.configs.recommended,
	...ts.configs.recommended,
	...svelte.configs.recommended,
	prettier,
	...svelte.configs.prettier,
	{
		languageOptions: { globals: { ...globals.browser } }
	},
	{
		files: ['**/*.svelte', '**/*.svelte.ts'],
		languageOptions: {
			parserOptions: { projectService: true, extraFileExtensions: ['.svelte'], parser: ts.parser }
		}
	},
	{
		rules: {
			// Types do the job; ESLint's own check does not know TypeScript's globals.
			'no-undef': 'off',
			// The app lives below the fixed base `/ui` (`#lib/base.ts`), and its links and `goto`
			// calls are built from it (`#lib/navigation.ts`), not by SvelteKit's `resolve()`. The rule
			// ran only for SvelteKit 1 and 2 until eslint-plugin-svelte 3.24.
			'svelte/no-navigation-without-resolve': 'off'
		}
	}
);
