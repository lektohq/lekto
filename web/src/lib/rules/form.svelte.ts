/**
 * What the editors of every rule share, a document's and a mail's, new or changed: the form is
 * checked before it goes to the API, its problems stand by their keys (`errors`) and as one
 * line above the buttons (`general`), and a save the API refused puts its problems there too,
 * each next to the block it names.
 */
import { toast } from 'svelte-sonner';
import type { FieldDefinition } from '#lib/masterdata.svelte.ts';
import { m } from '#lib/paraglide/messages.js';
import { problemText } from '#lib/rules/describe.ts';
import { saveErrors, type SaveErrors } from '#lib/rules/errors.ts';
import { validate, type RuleModel } from '#lib/rules/model.ts';

export class RuleForm {
	/** The problems by key, as `validate` and `saveErrors` give them. */
	errors = $state<Record<string, string>>({});
	/** What belongs to no block. */
	general = $state<string | null>(null);
	/** While a save is on its way. */
	busy = $state(false);

	/** Whether the form holds: `problems` in words, by key; any are shown. */
	show(problems: Record<string, string>): boolean {
		this.errors = problems;
		this.general = Object.keys(problems).length > 0 ? m.rule_form_invalid() : null;
		return this.general === null;
	}

	/** Whether `model` holds; else its problems are shown. */
	check(model: RuleModel, fields: readonly FieldDefinition[]): boolean {
		return this.show(
			Object.fromEntries(
				Object.entries(validate(model, fields)).map(([key, entry]) => [key, problemText(entry)])
			)
		);
	}

	/** Save through `save`: what it returns (with a toast), or null with the API's problems
	 * shown beside the blocks of `model`. */
	save<T>(model: RuleModel, save: () => Promise<T>): Promise<T | null> {
		return this.saveAt(save, (error) => saveErrors(error, model));
	}

	/** The same for any kind of rule: `placed` says where the API's problems belong. */
	async saveAt<T>(
		save: () => Promise<T>,
		placed: (error: unknown) => SaveErrors
	): Promise<T | null> {
		this.busy = true;
		try {
			const saved = await save();
			toast.success(m.rule_saved());
			return saved;
		} catch (error) {
			const { byKey, general } = placed(error);
			this.errors = byKey;
			this.general = general ?? (Object.keys(byKey).length > 0 ? m.rule_form_invalid() : null);
			return null;
		} finally {
			this.busy = false;
		}
	}
}
