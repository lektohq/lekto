<script lang="ts">
	import SearchSelect from '#lib/components/SearchSelect.svelte';
	import Select from '#lib/components/Select.svelte';
	import { withChoice } from '#lib/components/rules/options.ts';
	import {
		flagOptions,
		importanceOptions,
		keywordOptions,
		typedKeyword
	} from '#lib/mail-traits.ts';
	import { m } from '#lib/paraglide/messages.js';

	// The value of what a mail was marked with, wherever a rule names it (web/DESIGN.md, "Mail
	// rules": one set of parts for every rule): the condition of a document rule on the mail a
	// document came with, the condition of a mail rule, and a mail rule's step on the server.
	// The importance and the flag are a choice ("Bitte wählen …" first, a value no longer known
	// kept and named); a keyword is searched among those known, or typed as IMAP can carry it.
	let {
		trait,
		value,
		keywords = [],
		label,
		invalid = false,
		onchange
	}: {
		trait: 'importance' | 'flag' | 'keyword';
		value: string;
		/** The keywords to offer: a mailbox's for its rule, those of every mailbox for a
		 * document rule (it has no mailbox). */
		keywords?: readonly string[];
		label: string;
		invalid?: boolean;
		onchange: (value: string) => void;
	} = $props();
</script>

{#if trait === 'keyword'}
	<SearchSelect
		aria-label={label}
		aria-invalid={invalid || undefined}
		title={m.mail_keyword_title()}
		{value}
		options={keywordOptions(keywords, value)}
		placeholder={m.rule_choose()}
		create={typedKeyword}
		createLabel={m.mail_keyword_use}
		{onchange}
	/>
{:else}
	<Select
		aria-label={label}
		aria-invalid={invalid || undefined}
		{value}
		options={withChoice(trait === 'importance' ? importanceOptions() : flagOptions(), value)}
		{onchange}
	/>
{/if}
