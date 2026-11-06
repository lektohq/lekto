// The colour of the browser's and the installed app's bars (`<meta name="theme-color">`): the
// header's ground (`--card`), light or dark as the app shows itself. `static/theme.js` sets it
// before the first paint with the same values; `tests/app.test.ts` holds both to the tokens.
export const THEME_COLORS = { light: '#ffffff', dark: '#181c1b' } as const;

export function setThemeColor(dark: boolean): void {
	document
		.querySelector('meta[name="theme-color"]')
		?.setAttribute('content', dark ? THEME_COLORS.dark : THEME_COLORS.light);
}
