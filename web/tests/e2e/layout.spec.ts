// The layout rules of web/DESIGN.md in a browser, for every area at a phone's, a laptop's and a
// desktop's width: nothing scrolls sideways, every control is a finger's size on the phone (44
// pixels, a larger invisible hit area counts) and at least 24 pixels wider, and no page logs an
// error. Every area, with something in it: the spec creates what the pages show (a contact, a
// type with a title pattern, a tag, a rule, a webhook, a paused mailbox, a document) and
// deletes it again, so that it measures the same on an empty instance and on a used one. And
// every frame a page opens, one of each: the navigation sheet and the filter sheet of the
// phone, a dialog, a form dialog, an editor, a question, a menu. Signs in as the admin of the
// environment, as `areas.spec.ts` does. CI runs it (`.github/workflows/ci.yml`, job `layout`).
import { expect, test, type APIRequestContext, type Locator, type Page } from '@playwright/test';

const ADMIN = process.env.LEKTO_ADMIN_USERNAME ?? 'admin';
const ADMIN_PASSWORD = process.env.LEKTO_ADMIN_PASSWORD ?? '';
const NAME = `e2e-layout-${Date.now()}`;
const PDF = `%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]>>endobj
trailer<</Root 1 0 R>>
%%EOF
% ${NAME}`;

const PATHS = [
	'/ui/',
	'/ui/inbox',
	'/ui/documents',
	'/ui/spaces',
	'/ui/rules',
	'/ui/rules/new',
	'/ui/rules?kind=mail',
	'/ui/rules/mail/new',
	'/ui/webhooks',
	'/ui/webhooks/new',
	'/ui/system',
	'/ui/system?tab=classifier',
	'/ui/system?tab=search',
	'/ui/system?tab=jobs',
	'/ui/system?tab=intake',
	'/ui/admin/master-data',
	'/ui/admin/master-data?tab=document-types',
	'/ui/admin/master-data?tab=tags',
	'/ui/admin/master-data?tab=fields',
	'/ui/admin/master-data?tab=identifiers',
	'/ui/admin/users',
	'/ui/settings'
];

let api: APIRequestContext;
let csrf = '';
const made = { contact: '', type: '', tag: '', rule: '', webhook: '', mailbox: '', document: '' };

async function call(method: 'post' | 'patch' | 'delete', path: string, data?: object) {
	const response = await api[method](`/api/v1${path}`, {
		headers: { 'X-CSRF-Token': csrf },
		data
	});
	expect(response.ok(), `${method} ${path}: ${await response.text()}`).toBe(true);
	return response.status() === 204 ? null : await response.json();
}

/** The pages of what the spec made: lists show it, and each has a page of its own. */
function madePaths(): string[] {
	return [
		`/ui/documents?contact=${made.contact}`,
		`/ui/documents/${made.document}`,
		`/ui/documents/${made.document}?tab=properties`,
		`/ui/documents/${made.document}?tab=processing`,
		`/ui/rules/${made.rule}`,
		`/ui/rules/${made.rule}/edit`,
		`/ui/webhooks/${made.webhook}`,
		`/ui/webhooks/${made.webhook}/edit`,
		`/ui/system/mailboxes/${made.mailbox}`
	];
}

const WIDTHS = [
	{ name: 'phone', width: 390, height: 844, target: 44 },
	{ name: 'laptop', width: 1024, height: 768, target: 24 },
	{ name: 'desktop', width: 1440, height: 900, target: 24 }
];

/** What sticks out of `root` sideways (the page, or a frame open above it), and its controls
 * smaller than `target` (with their hit area). */
async function measure(root: Locator, target: number) {
	return root.evaluate((root, target) => {
		const page = root === document.documentElement;
		const overflow = page
			? document.documentElement.scrollWidth - window.innerWidth
			: root.scrollWidth - root.clientWidth;
		const small: string[] = [];
		const controls = root.querySelectorAll<HTMLElement>(
			'a[href], button, [role="button"], [role="menuitem"], input:not([type="hidden"]), select, textarea, [role="switch"], [role="combobox"]'
		);
		const px = (value: string) => (value.endsWith('px') ? parseFloat(value) : 0);
		for (const element of controls) {
			const box = element.getBoundingClientRect();
			if (box.width === 0 || box.height === 0) continue;
			if (element.closest('[aria-hidden="true"], .sr-only, [data-inline], p, dd')) continue;
			let [w, h] = [box.width, box.height];
			// A field inside its label or its frame (the search box, the date input; no taller than a
			// field) takes the pointer on the whole of it.
			if (element.matches('input, select, textarea')) {
				const parent = element.parentElement;
				const frame =
					element.closest('label') ??
					(parent &&
					parent.querySelectorAll('a[href], button, input, select, textarea').length === 1 &&
					parent.getBoundingClientRect().height <= 64
						? parent
						: null);
				if (frame) {
					const outer = frame.getBoundingClientRect();
					[w, h] = [Math.max(w, outer.width), Math.max(h, outer.height)];
				}
			}
			// A larger invisible hit area (`after:absolute after:-inset-*`) counts: around the
			// element when it is positioned, else around the box it is placed in.
			const after = getComputedStyle(element, '::after');
			if (after.position === 'absolute' && after.content !== 'none') {
				const placed = getComputedStyle(element).position !== 'static';
				const base = placed ? box : (element.offsetParent?.getBoundingClientRect() ?? box);
				w = Math.max(w, base.width - px(after.left) - px(after.right));
				h = Math.max(h, base.height - px(after.top) - px(after.bottom));
			}
			if (w + 0.5 < target || h + 0.5 < target) {
				const name = (element.getAttribute('aria-label') ?? element.textContent ?? '').trim();
				small.push(
					`${element.tagName.toLowerCase()} ${Math.round(w)}×${Math.round(h)} ${name.slice(0, 40)}`
				);
			}
		}
		return { overflow, small };
	}, target);
}

/** A frame a page opens above itself: where, how it opens, and how it goes again. */
interface Frame {
	name: string;
	path: () => string;
	open: (page: Page) => Promise<void>;
	/** Only on a phone (the sheets). */
	phone?: boolean;
}

const FRAMES: Frame[] = [
	{
		name: 'navigation sheet',
		path: () => '/ui/documents',
		open: (page) => page.getByRole('button', { name: 'Open navigation' }).click(),
		phone: true
	},
	{
		name: 'filter sheet',
		path: () => '/ui/documents',
		open: (page) => page.getByRole('button', { name: 'Filters', exact: true }).click(),
		phone: true
	},
	{
		name: 'dialog (upload)',
		path: () => '/ui/inbox',
		open: (page) => page.getByRole('button', { name: 'Upload', exact: true }).first().click()
	},
	{
		name: 'form dialog (new space)',
		path: () => '/ui/spaces',
		open: (page) => page.getByRole('button', { name: 'New space' }).click()
	},
	{
		name: 'editor (contact)',
		path: () => '/ui/admin/master-data',
		open: (page) =>
			page
				.getByRole('button', { name: new RegExp(`${NAME} Muster`) })
				.first()
				.click()
	},
	{
		name: 'question (delete a webhook)',
		path: () => `/ui/webhooks/${made.webhook}`,
		open: (page) => page.getByRole('button', { name: new RegExp(`^Delete ${NAME}`) }).click()
	},
	{
		name: 'menu (more of a document)',
		path: () => `/ui/documents/${made.document}`,
		open: (page) => page.getByRole('button', { name: 'More actions', exact: true }).click()
	}
];

/** The frame that lies on top: a dialog, a sheet, a question or a menu. */
const frameOf = (page: Page) =>
	page.locator('[role="dialog"], [role="alertdialog"], [role="menu"]').last();

test.beforeAll(async ({ playwright, baseURL }) => {
	test.skip(!ADMIN_PASSWORD, 'LEKTO_ADMIN_PASSWORD is not set');
	// Without OCR programs the document turns red only after the node's retries.
	test.setTimeout(240_000);
	api = await playwright.request.newContext({ baseURL });
	const login = await api.post('/api/v1/auth/login', {
		data: { username: ADMIN, password: ADMIN_PASSWORD }
	});
	expect(login.status(), await login.text()).toBe(200);
	csrf = ((await login.json()) as { csrf_token: string }).csrf_token;
	made.contact = (await call('post', '/contacts', { name: `${NAME} Muster GmbH` })).id;
	made.tag = (await call('post', '/tags', { name: `${NAME} tag` })).id;
	// A type with a title pattern has a rule of its own, which the list of rules shows.
	made.type = (
		await call('post', '/document-types', { name: `${NAME} type`, title_pattern: '{{ contact }}' })
	).id;
	made.rule = (
		await call('post', '/rules', {
			name: `${NAME} rule`,
			triggers: ['change'],
			conditions: { all: [{ field: 'contact', op: 'missing' }] },
			actions: [{ type: 'add_tags', tag_ids: [made.tag] }],
			enabled: false
		})
	).id;
	made.webhook = (
		await call('post', '/webhooks', {
			name: `${NAME} webhook`,
			url: 'https://hooks.example.invalid/lekto',
			active: false
		})
	).id;
	made.mailbox = (
		await call('post', '/mailboxes', {
			name: `${NAME} mailbox`,
			host: 'imap.example.invalid',
			port: 993,
			security: 'tls',
			username: 'john.doe',
			password: '12345',
			enabled: false
		})
	).id;
	const upload = await api.post('/api/v1/documents', {
		headers: { 'X-CSRF-Token': csrf },
		multipart: {
			file: { name: `${NAME}.pdf`, mimeType: 'application/pdf', buffer: Buffer.from(PDF) }
		}
	});
	expect(upload.status(), await upload.text()).toBe(202);
	made.document = (await upload.json()).id;
	// Out of processing (green, yellow or red, depending on the services), then what it shows.
	await expect
		.poll(async () => (await (await api.get(`/api/v1/documents/${made.document}`)).json()).lane, {
			timeout: 200_000
		})
		.not.toBeNull();
	await call('patch', `/documents/${made.document}`, {
		contact_id: made.contact,
		document_type_id: made.type,
		tag_ids: [made.tag],
		document_date: '2026-03-12'
	});
});

test.afterAll(async () => {
	if (!api) return;
	const gone = (path: string, id: string) =>
		id ? call('delete', `${path}/${id}`).catch(() => {}) : null;
	await gone('/documents', made.document);
	await gone('/mailboxes', made.mailbox);
	await gone('/webhooks', made.webhook);
	await gone('/rules', made.rule);
	await gone('/document-types', made.type);
	await gone('/tags', made.tag);
	await gone('/contacts', made.contact);
	await api.dispose();
});

for (const size of WIDTHS) {
	test(`every area holds the layout rules at ${size.width} px`, async ({ browser }) => {
		const context = await browser.newContext({
			viewport: { width: size.width, height: size.height },
			hasTouch: size.name === 'phone'
		});
		const page = await context.newPage();
		const problems: string[] = [];
		page.on('console', (message) => {
			// Missing services (search, models) answer 4xx/5xx on purpose; those are not page errors.
			if (message.type() === 'error' && !/status of [45]\d\d/.test(message.text()))
				problems.push(message.text());
		});
		page.on('pageerror', (error) => problems.push(error.message));

		await page.goto('/ui/login');
		await page.getByLabel('Username').fill(ADMIN);
		await page.getByLabel('Password').fill(ADMIN_PASSWORD);
		await page.getByRole('button', { name: 'Sign in' }).click();
		await page.waitForURL('**/ui/');

		const findings: string[] = [];
		for (const path of [...PATHS, ...madePaths()]) {
			await page.goto(path);
			await page.waitForLoadState('networkidle');
			const { overflow, small } = await measure(page.locator('html'), size.target);
			if (overflow > 1) findings.push(`${path}: ${overflow} px wider than the window`);
			for (const control of small) findings.push(`${path}: ${control}`);
		}
		// What a page opens above itself: the frame alone, the page behind it was measured.
		for (const frame of FRAMES) {
			if (frame.phone && size.name !== 'phone') continue;
			await page.goto(frame.path());
			await page.waitForLoadState('networkidle');
			await frame.open(page);
			const layer = frameOf(page);
			await layer.waitFor();
			// Let it come to rest: a sheet slides in.
			await page.waitForTimeout(400);
			const { overflow, small } = await measure(layer, size.target);
			if (overflow > 1) findings.push(`${frame.name}: ${overflow} px wider than itself`);
			for (const control of small) findings.push(`${frame.name}: ${control}`);
		}
		expect(findings).toEqual([]);
		expect(problems).toEqual([]);
		await context.close();
	});
}
