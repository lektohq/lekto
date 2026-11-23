/// <reference types="node" />
// A Node build script: the Node types, which the app itself does not see.
import { createReadStream, existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { BASE } from './src/lib/base.ts';

// PDF.js loads decoders (JBIG2, JPEG 2000, colour profiles), the standard fonts, the character
// maps and the CMYK profile (`iccs`: without it, CMYK colours are reckoned roughly and shift) at
// run time. They are served from the app itself under `pdfjs/`; nothing comes from a CDN.
const FOLDERS = ['wasm', 'standard_fonts', 'cmaps', 'iccs'];

// The sandbox of PDF.js (its JavaScript in forms) runs on QuickJS; the viewer runs no script of a
// PDF, so its half a megabyte stays out.
const LEFT_OUT = /^(?:quickjs|LICENSE.*QUICKJS)/i;

/** @returns {import('vite').Plugin} */
export function pdfjsAssets() {
	const root = dirname(createRequire(import.meta.url).resolve('pdfjs-dist/package.json'));
	/** @type {Set<string> | null} */
	let listed = null;
	/** The files it serves, read once. */
	const files = () =>
		(listed ??= new Set(
			FOLDERS.flatMap((folder) =>
				readdirSync(join(root, folder))
					.filter((name) => !LEFT_OUT.test(name))
					.map((name) => `${folder}/${name}`)
			)
		));
	return {
		name: 'lekto-pdfjs-assets',
		// The pages load them: the client's build, not the server's.
		applyToEnvironment: (environment) => environment.name === 'client',
		configureServer(server) {
			server.middlewares.use((request, response, next) => {
				const prefix = `${BASE}/pdfjs/`;
				const path = (request.url ?? '').split('?')[0];
				const name = path.startsWith(prefix) ? path.slice(prefix.length) : '';
				if (!files().has(name)) return next();
				const file = join(root, name);
				if (!existsSync(file) || !statSync(file).isFile()) return next();
				if (name.endsWith('.wasm')) response.setHeader('content-type', 'application/wasm');
				createReadStream(file).pipe(response);
			});
		},
		generateBundle() {
			for (const name of files()) {
				this.emitFile({
					type: 'asset',
					fileName: `pdfjs/${name}`,
					source: readFileSync(join(root, name))
				});
			}
		}
	};
}
