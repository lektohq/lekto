// Sets the colour scheme before the app starts, so that a dark page does not flash white.
// The key and values are those of mode-watcher, which takes over once the app runs; the colour
// of the browser's bars follows it (`lib/theme-color.ts`, the same values).
//
// Without browser storage (blocked site data, a WebView without DOM storage) it first puts one in
// memory in its place: mode-watcher and Paraglide read `localStorage` unguarded, and the app would
// not start at all. What is kept there lasts until the page is loaded again.
(function () {
	var storage = null;
	try {
		storage = window.localStorage;
	} catch {
		// Blocked site data: reading it throws.
	}
	if (!storage) {
		var items = new Map();
		storage = {
			get length() {
				return items.size;
			},
			key: function (index) {
				var name = Array.from(items.keys())[index];
				return name === undefined ? null : name;
			},
			getItem: function (name) {
				name = String(name);
				return items.has(name) ? items.get(name) : null;
			},
			setItem: function (name, value) {
				items.set(String(name), String(value));
			},
			removeItem: function (name) {
				items.delete(String(name));
			},
			clear: function () {
				items.clear();
			}
		};
		try {
			Object.defineProperty(window, 'localStorage', { value: storage, configurable: true });
		} catch {
			// A browser that does not let it be replaced keeps its own.
		}
	}
	var mode = null;
	try {
		mode = storage.getItem('mode-watcher-mode');
	} catch {
		// Storage can refuse a read; follow the system then.
	}
	var dark =
		mode === 'dark' ||
		(mode !== 'light' && window.matchMedia('(prefers-color-scheme: dark)').matches);
	document.documentElement.classList.toggle('dark', dark);
	document.documentElement.style.colorScheme = dark ? 'dark' : 'light';
	var bar = document.querySelector('meta[name="theme-color"]');
	if (bar) bar.setAttribute('content', dark ? '#181c1b' : '#ffffff');
})();
