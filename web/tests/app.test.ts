// The installed app (web/DESIGN.md, "App"): what the service worker keeps (only the app's own
// files, never an answer of the API), the manifest, its icons, and the colour of the bars from
// the tokens.
import { describe, expect, it } from 'vitest';
import css from '../src/app.css?raw';
import html from '../src/app.html?raw';
import themeScript from '../static/theme.js?raw';
import manifestText from '../static/manifest.webmanifest?raw';
import {
	appFiles,
	belongsTo,
	isShareId,
	pageFiles,
	pageKey,
	sharedKey,
	sharePath,
	shellPaths,
	strategy
} from '#lib/app-cache.ts';
import { BASE } from '#lib/base.ts';
import { ACCEPT, skipReason } from '#lib/intake.ts';
import { THEME_COLORS } from '#lib/theme-color.ts';

const sources = import.meta.glob<string>('/src/**/*.svelte', {
	query: '?raw',
	import: 'default',
	eager: true
});
const ORIGIN = 'https://lekto.example.org';
const SHELL = new Set(shellPaths(['favicon.svg', 'theme.js', 'manifest.webmanifest'], BASE));
const icons = import.meta.glob<string>('/static/*.png', {
	query: '?inline',
	import: 'default',
	eager: true
});

function decide(path: string, init: { method?: string; mode?: string; origin?: string } = {}) {
	return strategy(
		{
			url: `${init.origin ?? ORIGIN}${path}`,
			method: init.method ?? 'GET',
			mode: init.mode ?? 'cors'
		},
		ORIGIN,
		BASE,
		SHELL
	);
}

describe('the service worker keeps only the app', () => {
	it.each([
		'/api/v1/documents',
		'/api/v1/documents/1/archive',
		'/api/v1/documents/1/pages/1',
		'/api/v1/auth/me',
		'/api/v1/events',
		'/api'
	])('never keeps %s', (path) => {
		expect(decide(path)).toBe('network');
		expect(decide(path, { mode: 'navigate' })).toBe('network');
	});

	it('leaves other methods and other sites alone', () => {
		expect(decide(`${BASE}/_app/immutable/entry/app.js`, { method: 'POST' })).toBe('network');
		expect(decide(`${BASE}/favicon.svg`, { origin: 'https://elsewhere.example' })).toBe('network');
		expect(decide('/elsewhere/page', { mode: 'navigate' })).toBe('network');
	});

	it('keeps the hashed files and the files of the shell', () => {
		expect(decide(`${BASE}/_app/immutable/chunks/Bx1y2z.js`)).toBe('file');
		expect(decide(`${BASE}/_app/immutable/assets/0.css`)).toBe('file');
		expect(decide(`${BASE}/favicon.svg`)).toBe('file');
		expect(decide(`${BASE}/manifest.webmanifest`)).toBe('file');
	});

	it('asks the network for the version, the worker and PDF.js', () => {
		expect(decide(`${BASE}/_app/version.json`)).toBe('network');
		expect(decide(`${BASE}/service-worker.js`)).toBe('network');
		expect(decide(`${BASE}/pdfjs/cmaps/Adobe-Japan1-UCS2.bcmap`)).toBe('network');
	});

	it('loads pages from the network, the kept page only without one', () => {
		expect(decide(`${BASE}/`, { mode: 'navigate' })).toBe('page');
		expect(decide(`${BASE}/documents/42`, { mode: 'navigate' })).toBe('page');
		expect(pageKey(BASE)).toBe(`${BASE}/`);
	});

	it('names the files of the shell below the base, without PDF.js', () => {
		expect(shellPaths(['favicon.svg', '/theme.js', 'pdfjs/wasm/openjpeg.wasm'], BASE)).toEqual([
			`${BASE}/favicon.svg`,
			`${BASE}/theme.js`
		]);
	});

	it('takes the files the page loads first from its links', () => {
		const page = `<link rel="icon" href="${BASE}/favicon.svg">
			<link href="${BASE}/_app/immutable/entry/start.CZ.js" rel="modulepreload">
			<link href="${BASE}/_app/immutable/assets/0.yn.css" rel="stylesheet">
			<link href="https://elsewhere.example/x.js" rel="modulepreload">`;
		expect(pageFiles(page, BASE)).toEqual([
			`${BASE}/_app/immutable/entry/start.CZ.js`,
			`${BASE}/_app/immutable/assets/0.yn.css`
		]);
	});

	it('keeps of what the page loaded only its own hashed files', () => {
		expect(
			appFiles(
				[
					`${ORIGIN}${BASE}/_app/immutable/nodes/3.js`,
					`${ORIGIN}/api/v1/documents/1/thumbnail`,
					`https://elsewhere.example${BASE}/_app/immutable/x.js`,
					'not a url'
				],
				ORIGIN,
				BASE
			)
		).toEqual([`${BASE}/_app/immutable/nodes/3.js`]);
	});
});

/** The light and the dark value of a token in app.css. */
function token(name: string): [string, string] {
	const values = [...css.matchAll(new RegExp(`--${name}:\\s*([^;]+);`, 'g'))].map((m) =>
		m[1].trim()
	);
	return [values[0], values[1]];
}

/** Width and height of a PNG given as a data URL. */
function pngSize(dataUrl: string): [number, number] {
	const bytes = Uint8Array.from(atob(dataUrl.split(',')[1]), (c) => c.charCodeAt(0));
	const view = new DataView(bytes.buffer);
	return [view.getUint32(16), view.getUint32(20)];
}

describe('the manifest', () => {
	const manifest = JSON.parse(manifestText) as {
		id: string;
		start_url: string;
		scope: string;
		display: string;
		background_color: string;
		theme_color: string;
		icons: { src: string; sizes: string; type: string; purpose: string }[];
	};

	it('starts the app below the base and keeps the sign-in by a provider in it', () => {
		expect(manifest.id).toBe(`${BASE}/`);
		expect(manifest.start_url).toBe(`${BASE}/`);
		// The answer of OpenID Connect comes back below /api: it stays in the app.
		expect(manifest.scope).toBe('/');
		expect(manifest.display).toBe('standalone');
	});

	it('takes its colours from the tokens', () => {
		expect(manifest.background_color).toBe(token('background')[0]);
		expect(manifest.theme_color).toBe(THEME_COLORS.light);
	});

	it('names icons that exist in the sizes it says, one of them maskable', () => {
		for (const icon of manifest.icons) {
			expect(icon.src.startsWith(`${BASE}/`)).toBe(true);
			const file = `/static/${icon.src.slice(BASE.length + 1)}`;
			if (icon.type === 'image/png') {
				const [width, height] = icon.sizes.split('x').map(Number);
				expect(icons[file], file).toBeDefined();
				expect(pngSize(icons[file])).toEqual([width, height]);
			}
		}
		expect(manifest.icons.some((icon) => icon.purpose === 'maskable')).toBe(true);
		expect(manifest.icons.some((icon) => icon.sizes === '512x512' && icon.purpose === 'any')).toBe(
			true
		);
	});

	it('is linked from the page with the colour of the bars', () => {
		expect(html).toContain('rel="manifest" href="%sveltekit.assets%/manifest.webmanifest"');
		expect(html).toContain(`<meta name="theme-color" content="${THEME_COLORS.light}" />`);
	});
});

describe('the colour of the bars', () => {
	it("is the header's ground, light and dark", () => {
		expect([THEME_COLORS.light, THEME_COLORS.dark]).toEqual(token('card'));
	});

	it('is set before the first paint with the same values', () => {
		expect(themeScript).toContain(`'${THEME_COLORS.dark}'`);
		expect(themeScript).toContain(`'${THEME_COLORS.light}'`);
	});
});

describe('the safe areas of the installed app', () => {
	it('reaches under the notch and the home indicator', () => {
		expect(html).toContain('viewport-fit=cover');
	});

	// A surface that covers the whole phone screen or stands at its bottom edge keeps the insets
	// free: full-screen editors, bars stuck to the bottom, sheets from below, fixed buttons.
	const EDGE =
		/\bh-dvh max-h-dvh\b|\bsticky bottom-0\b|\bfixed\b[^'"]*\bbottom-|data-\[side=bottom\]:inset-x-0/;

	it.each(Object.entries(sources).filter(([, source]) => EDGE.test(source)))(
		'%s keeps the safe area free',
		(_, source) => {
			expect(source).toContain('env(safe-area-inset-');
		}
	);
});

describe('sharing with the installed app', () => {
	const manifest = JSON.parse(manifestText) as {
		share_target: {
			action: string;
			method: string;
			enctype: string;
			params: { files: { name: string; accept: string[] }[] };
		};
	};

	it('keeps what is posted to the share target, nothing else that is posted', () => {
		expect(decide(sharePath(BASE), { method: 'POST', mode: 'navigate' })).toBe('share');
		expect(decide(`${BASE}/inbox`, { method: 'POST', mode: 'navigate' })).toBe('network');
		expect(decide('/api/v1/documents', { method: 'POST' })).toBe('network');
		expect(decide(sharePath(BASE), { mode: 'navigate' })).toBe('page');
	});

	it('names a share by a random id only', () => {
		const id = '0b6f1c1e-6a8a-4a3e-9d0a-3b8c2a1f4e55';
		expect(isShareId(id)).toBe(true);
		expect(isShareId('Rechnung.pdf')).toBe(false);
		expect(isShareId(null)).toBe(false);
		expect(belongsTo(sharedKey(BASE, id, 2), BASE, id)).toBe(true);
		expect(belongsTo(sharedKey(BASE, id, 2), BASE, id.replace('0b', '1b'))).toBe(false);
	});

	it('posts files to the share target, of the kinds an upload takes', () => {
		const target = manifest.share_target;
		expect(target.action).toBe(sharePath(BASE));
		expect([target.method, target.enctype]).toEqual(['POST', 'multipart/form-data']);
		const [files] = target.params.files;
		expect(files.name).toBe('files');
		for (const kind of files.accept) {
			const taken = kind.startsWith('.') ? skipReason(`file${kind}`, '') : skipReason('file', kind);
			expect(taken, kind).toBeNull();
		}
		for (const kind of ACCEPT.split(',')) expect(files.accept).toContain(kind);
	});
});
