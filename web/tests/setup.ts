import { configure } from '@testing-library/svelte';
import { afterEach, beforeEach, vi } from 'vitest';
import { takeUnrouted } from '#lib/testing/api.ts';

// How long `waitFor` and `find*` wait for what a test expects: a busy runner (a CI shard, a full
// run beside the dev instance) takes longer than the default second for a dialog to close or a
// reload after a burst of events (300 ms) to land. A test that passes does not wait longer; the
// deadline counts only for one that would fail. Not per test (Tobi, 10.11.2026).
configure({ asyncUtilTimeout: 10_000 });

// A dialog or menu of bits-ui takes the pointer from the page while it is open. One that a test
// leaves open would take it from the next test of the file too: every test starts with it. No
// test switches the check of the pointer off for that (`pointerEventsCheck`): it is what finds a
// dialog that does not give the pointer back.
afterEach(() => {
	document.body.style.pointerEvents = '';
});

// A fake API answers only what a test routes (`lib/testing/api.ts`): a request it has no route
// for is a wrong path or method, or one the test did not expect, and fails the test (WT1-05).
// Checked once the test finished, after every `afterEach`: a throw there skipped the cleanup.
beforeEach(({ onTestFinished }) => {
	takeUnrouted();
	onTestFinished(() => {
		const missed = takeUnrouted();
		if (missed.length > 0)
			throw new Error(`requests without a route in the fake: ${missed.join(', ')}`);
	});
});

// A component that binds to a plain object, not to `$state`, shows none of the object's changes:
// Svelte warns `binding_property_non_reactive`. A test that hands one over (a rule's model
// without `$state`) tests a view that cannot follow; it fails (WT2-07).
const unreactive: string[] = [];
const warn = console.warn;
console.warn = (...args: unknown[]) => {
	if (String(args[0]).includes('binding_property_non_reactive')) unreactive.push(String(args[0]));
	warn(...args);
};
beforeEach(({ onTestFinished }) => {
	unreactive.length = 0;
	onTestFinished(() => {
		const found = unreactive.splice(0);
		if (found.length > 0) throw new Error(`bound to a plain object: ${found[0]}`);
	});
});

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
