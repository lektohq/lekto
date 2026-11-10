import { configure } from '@testing-library/svelte';
import { vi } from 'vitest';

// How long `waitFor` and `find*` wait for what a test expects: a busy runner (a CI shard, a full
// run beside the dev instance) takes longer than the default second for a dialog to close or a
// reload after a burst of events (300 ms) to land. A test that passes does not wait longer; the
// deadline counts only for one that would fail. Not per test (Tobi, 10.11.2026).
configure({ asyncUtilTimeout: 10_000 });

// jsdom lacks a few browser APIs the components use.

if (!window.matchMedia) {
	window.matchMedia = (query: string) =>
		({
			matches: false,
			media: query,
			onchange: null,
			addListener: () => {},
			removeListener: () => {},
			addEventListener: () => {},
			removeEventListener: () => {},
			dispatchEvent: () => false
		}) as MediaQueryList;
}

if (!window.ResizeObserver) {
	window.ResizeObserver = class {
		observe() {}
		unobserve() {}
		disconnect() {}
	};
}

// The list of a `Select` (bits-ui) captures the pointer while it opens.
if (!Element.prototype.hasPointerCapture) {
	Element.prototype.hasPointerCapture = () => false;
	Element.prototype.setPointerCapture = () => {};
	Element.prototype.releasePointerCapture = () => {};
}

if (!Element.prototype.scrollIntoView) {
	Element.prototype.scrollIntoView = () => {};
}

// CodeMirror reads the selection in a shadow root through it where `getSelection` is missing.
if (!document.execCommand) {
	document.execCommand = () => false;
}

// CodeMirror needs a browser's layout; component tests edit templates in a plain text area.
vi.mock('#lib/templates/codemirror.ts', () => import('#lib/testing/fake-template-editor.ts'));

// The date picker (bits-ui) needs a browser's layout; component tests type a plain date input.
vi.mock('#lib/components/DateInput.svelte', () => import('#lib/testing/FakeDateInput.svelte'));
