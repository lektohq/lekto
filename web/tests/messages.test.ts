// Every text exists in every language, with the same placeholders.
import { describe, expect, it } from 'vitest';
import de from '../messages/de.json';
import en from '../messages/en.json';

const catalogues: Record<string, Record<string, string>> = { de, en };

function keys(catalogue: Record<string, string>): string[] {
	return Object.keys(catalogue)
		.filter((key) => key !== '$schema')
		.sort();
}

function placeholders(text: string): string[] {
	return [...text.matchAll(/\{(\w+)\}/g)].map((match) => match[1]).sort();
}

// A text with a number names what it counts in the plural ("{count} Dokumente"), and for 1 the
// caller takes its singular, `<key>_one` ("1 Dokument"): never "1 Dokumente". A text with a
// number that needs none stands here: nothing counted follows the number ("Seiten: {count}"),
// the number is never 1 (`merge_title`, from two on), or its singular has a name of its own
// (`master_topic_one` beside `master_topics_many`). A new text with `{count}` gets its `_one`,
// or its place in this list with the reason in mind.
const NO_SINGULAR: ReadonlySet<string> = new Set([
	'automation_custom_decided_one_field',
	'automation_custom_more',
	'automation_first_green',
	'automation_first_red',
	'automation_first_yellow',
	'automation_flow_done',
	'automation_flow_failed',
	'automation_flow_open',
	'automation_flow_review',
	'automation_flow_running',
	'bulk_all_hits_capped',
	'bulk_details_more',
	'bulk_merge_many',
	'bulk_select_all',
	'bulk_skipped',
	'classifier_history_examples',
	'classifier_signal_of',
	'details_characters_one_page',
	'details_characters_total',
	'details_page_characters',
	'details_separate_on_pages',
	'doc_pages',
	'doc_pages_short',
	'documents_total',
	'due_in',
	'expected_documents',
	'expected_every_days',
	'expected_spread',
	'facet_all_contacts',
	'facet_all_tags',
	'facet_all_types',
	'facet_chosen',
	'facet_month_count',
	'facet_undated',
	'facts_more',
	'filters_expand_active',
	'filters_show',
	'holders_cases_first',
	'holders_cases_open',
	'holders_of',
	'icon_search_more',
	'inbox_all_seen_done',
	'inbox_badge_new',
	'inbox_badge_processing',
	'inbox_badge_red',
	'inbox_badge_total',
	'inbox_badge_yellow',
	'inbox_open_fields',
	'mail_interval_hours',
	'mail_interval_minutes',
	'mail_rule_dry_run_attachments',
	'mail_rule_preview_before',
	'mail_rule_preview_nothing',
	'mail_rule_preview_waiting',
	'mail_test_ok',
	'mailbox_hidden_documents',
	'mailbox_waiting_rule',
	'maintenance_queued_contacts',
	'maintenance_queued_documents',
	'maintenance_waiting',
	'master_alias_more',
	'master_contacts_many',
	'master_fields_many',
	'master_groups_more',
	'master_identifiers_many',
	'master_required_count',
	'master_topics_many',
	'master_types_many',
	'matrix_chip_signals',
	'merge_title',
	'open_confirm_recommended',
	'open_confirm_recommended_do',
	'open_confirm_recommended_title',
	'open_confirmed',
	'open_failed',
	'open_learned_at',
	'open_rejected',
	'overview_expected_more',
	'overview_failed_kind',
	'overview_lane_new',
	'overview_lane_red',
	'overview_lane_yellow',
	'page_edit_added',
	'page_edit_next_parts',
	'page_edit_parts_count',
	'prompt_attempts',
	'prompt_requests',
	'push_waiting_many',
	'push_waiting_new',
	'reason_recommend_confirm',
	'reason_recommend_confirm_named',
	'reason_recommend_reject_contacts',
	'reason_recommend_reject_foreign',
	'rule_preview_conflicts',
	'rule_preview_loading',
	'rule_preview_stopped',
	'search_total',
	'search_total_meaning',
	'selection_chip',
	'selection_selected',
	'stream_gap',
	'summary_characters',
	'summary_fields_partly',
	'tag_below',
	'token_scope_custom',
	'upload_summary_duplicates',
	'upload_summary_failed',
	'upload_summary_skipped',
	'upload_summary_uploaded',
	'user_delete_space',
	'webhook_failing',
	'webhook_volume_run',
	'webhook_volume_times',
	'webhook_volume_total_exact'
]);

// Help opens beside a label and is read in passing (DESIGN.md, "Help and tooltips"): about 200
// characters, and none above this. The one text that is longer describes a dialog.
const HELP_LIMIT = 220;
const NO_HELP: ReadonlySet<string> = new Set(['open_confirm_recommended_hint']);

describe('messages', () => {
	it('have a singular beside every text that counts something', () => {
		const counting = keys(de).filter(
			(key) => de[key as keyof typeof de].includes('{count}') && !key.endsWith('_one')
		);
		const missing = counting.filter((key) => !(`${key}_one` in de) && !NO_SINGULAR.has(key));
		expect(missing).toEqual([]);
		// The list holds only what it is for.
		const stale = [...NO_SINGULAR].filter((key) => !counting.includes(key) || `${key}_one` in de);
		expect(stale).toEqual([]);
	});

	it('have the same keys in every language', () => {
		expect(keys(de)).toEqual(keys(en));
	});

	it.each(Object.keys(catalogues))('are not empty in %s', (locale) => {
		const catalogue = catalogues[locale];
		const empty = keys(catalogue).filter((key) => !catalogue[key].trim());
		expect(empty).toEqual([]);
	});

	it.each(Object.keys(catalogues))('keep a help text short in %s', (locale) => {
		const catalogue = catalogues[locale];
		const long = keys(catalogue).filter(
			(key) => /_(info|hint)$/.test(key) && !NO_HELP.has(key) && catalogue[key].length > HELP_LIMIT
		);
		expect(long).toEqual([]);
	});

	it('use the same placeholders in every language', () => {
		const differing = keys(en).filter(
			(key) =>
				placeholders(en[key as keyof typeof en]).join() !==
				placeholders(de[key as keyof typeof de]).join()
		);
		expect(differing).toEqual([]);
	});
});
