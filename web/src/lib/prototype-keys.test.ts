// A key from outside a table (an address, the API of a newer Lekto) that names a member every
// object has (`toString`, `__proto__`) is unknown like any other, never the prototype's member
// (WT3-04; WG-01 broke the document list with one).
import { describe, expect, it } from 'vitest';
import { holderLabel, type Holder } from './facts.ts';
import { flagLabel, importanceLabel } from './mail-traits.ts';
import { m } from './paraglide/messages.js';
import { reasonText } from './reasons.ts';
import { own } from './utils.ts';
import { eventLabel } from './webhooks.ts';

const KEYS = ['__proto__', 'constructor', 'toString', 'valueOf', 'hasOwnProperty'];

describe('a key every object has', () => {
	it.each(KEYS)('is no entry of a table: %s', (key) => {
		expect(own({ known: 1 }, key)).toBeUndefined();
		expect(own({ known: 1 }, 'known')).toBe(1);
	});

	it.each(KEYS)('stands as it is where a name is looked up: %s', (key) => {
		expect(eventLabel(key)).toBe(key);
		expect(flagLabel(key)).toBe(key);
		expect(importanceLabel(key)).toBe(key);
		const holder = { kind: key, source: key, name: null } as unknown as Holder;
		expect(holderLabel(holder)).toBe(m.facts_holder({ holder: key, source: key }));
		const steps = reasonText({ code: 'still_running', params: { nodes: [key, 'ocr'] } });
		expect(steps).toContain(key);
		expect(steps).toContain(m.node_ocr());
	});

	it('names what the tables know', () => {
		expect(eventLabel('webhook.test')).toBe(m.event_test());
		expect(flagLabel('red')).toBe(m.mail_flag_red());
	});
});
