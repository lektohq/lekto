/* eslint-disable @typescript-eslint/ban-ts-comment */
// @ts-nocheck -- a Node build script; the project has no Node type definitions.
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';

// The API's documentation (`/api/v1/docs`, Swagger UI) loads its script and style from the app
// under `swagger/`, not from a CDN: the page runs in the API's origin, where the session cookie
// holds. The API names these paths (`SWAGGER_FILES` in the REST adapter's `app.py`).
const FILES = ['swagger-ui-bundle.js', 'swagger-ui.css'];

/** @returns {import('vite').Plugin} */
export function swaggerAssets() {
	const root = dirname(createRequire(import.meta.url).resolve('swagger-ui-dist/package.json'));
	return {
		name: 'lekto-swagger-assets',
		generateBundle() {
			for (const name of FILES) {
				this.emitFile({
					type: 'asset',
					fileName: `swagger/${name}`,
					source: readFileSync(join(root, name))
				});
			}
		}
	};
}
