/// <reference types="node" />
// A Node build script: the Node types, which the app itself does not see.
import { createReadStream, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { BASE } from './src/lib/base.ts';

// The API's documentation (`/api/v1/docs`, Swagger UI) loads its script and style from the app
// under `swagger/`, not from a CDN: the page runs in the API's origin, where the session cookie
// holds. The API names these paths (`SWAGGER_PATH` and `_docs` in the REST adapter's `app.py`).
const FILES = ['swagger-ui-bundle.js', 'swagger-ui.css'];

/** @returns {import('vite').Plugin} */
export function swaggerAssets() {
	const root = dirname(createRequire(import.meta.url).resolve('swagger-ui-dist/package.json'));
	return {
		name: 'lekto-swagger-assets',
		// The API's page loads them: the client's build, not the server's.
		applyToEnvironment: (environment) => environment.name === 'client',
		// Under `pnpm dev` too, as the built app serves them.
		configureServer(server) {
			server.middlewares.use((request, response, next) => {
				const prefix = `${BASE}/swagger/`;
				const path = (request.url ?? '').split('?')[0];
				const name = path.startsWith(prefix) ? path.slice(prefix.length) : '';
				if (!FILES.includes(name)) return next();
				response.setHeader('content-type', name.endsWith('.css') ? 'text/css' : 'text/javascript');
				createReadStream(join(root, name)).pipe(response);
			});
		},
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
