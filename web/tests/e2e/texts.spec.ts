// What the libraries say on a German page, read where a screen reader reads it: the names and
// values in the browser, not the source. The guards over the code see `m.date_previous_month()`
// passed to the calendar's button; the library laid "Previous" over it all the same (WY-03),
// and named the toaster's parts itself (WE-12). So this spec opens what the libraries draw, a
// date field with its calendar and a toast, and looks for the defaults known to be theirs. Signs
// in as the admin of the environment, as `layout.spec.ts` does; CI runs both
// (`.github/workflows/ci.yml`, job `layout`).
import { expect, test, type Page } from '@playwright/test';

const ADMIN = process.env.LEKTO_ADMIN_USERNAME ?? 'admin';
const ADMIN_PASSWORD = process.env.LEKTO_ADMIN_PASSWORD ?? '';

test.use({ locale: 'de-DE' });

/** What bits-ui and svelte-sonner call their parts unless told otherwise. One that is left on
 * purpose, with no option of the library, is not listed: the calendar's "Selected Date: …". */
const DEFAULTS = [
	/^Close toast$/,
	/^Notifications\b/,
	/^Event\b/,
	/^Empty$/,
	/^(?:day|month|year|hour|minute), ?$/,
	/^Previous$/,
	/^Next$/
];

/** Every name and value the page gives an element by an attribute. */
async function said(page: Page): Promise<string[]> {
	return page.evaluate(() => {
		const found = new Set<string>();
		for (const element of document.querySelectorAll('*'))
			for (const name of ['aria-label', 'aria-valuetext', 'title', 'alt', 'placeholder']) {
				const value = element.getAttribute(name);
				if (value) found.add(value);
			}
		return [...found];
	});
}

const english = (names: string[]) =>
	names.filter((name) => DEFAULTS.some((known) => known.test(name)));

test('the libraries speak the language of the UI', async ({ page }) => {
	await page.goto('/ui/login');
	await page.locator('input[autocomplete="username"]').fill(ADMIN);
	await page.locator('input[type="password"]').fill(ADMIN_PASSWORD);
	await page.keyboard.press('Enter');
	await page.waitForURL((url) => !url.pathname.endsWith('/login'));
	await expect(page.locator('html')).toHaveAttribute('lang', 'de');

	// The profile has a date field: its parts, then its calendar with the month buttons.
	await page.goto('/ui/settings');
	const pick = page.getByRole('button', { name: 'Im Kalender wählen' }).first();
	await expect(pick).toBeVisible();
	const field = await said(page);
	expect(field).toEqual(expect.arrayContaining(['Tag', 'Monat', 'Jahr']));
	expect(english(field)).toEqual([]);

	await pick.click();
	await expect(page.getByRole('button', { name: 'Voriger Monat' })).toBeVisible();
	await expect(page.getByRole('button', { name: 'Nächster Monat' })).toBeVisible();
	expect(english(await said(page))).toEqual([]);
	await page.keyboard.press('Escape');

	// Saving the profile as it is says so in a toast, with its ✕ and its region.
	await page.getByRole('button', { name: 'Speichern' }).first().click();
	await expect(page.locator('[data-sonner-toast]').first()).toBeVisible();
	const toast = await said(page);
	expect(toast).toContain('Meldung schließen');
	expect(english(toast)).toEqual([]);
});

test('the list of defaults knows its own', () => {
	expect(
		english(['Close toast', 'Event November 2026', 'day, ', 'Empty', 'Previous'])
	).toHaveLength(5);
	expect(english(['Meldung schließen', 'Geburtsdatum November 2026', 'Tag', 'leer'])).toEqual([]);
});
