/**
 * Asks before a dialog with a form closes over what was typed (web/DESIGN.md, "Saving and
 * leaving"). Escape, a click beside the dialog and its X close it by accident as easily as on
 * purpose: they ask first ("Verwerfen" goes on). "Abbrechen" and saving close it at once: the
 * person said what they want.
 *
 * The frame of the dialog holds one guard: it hears what the form's fields are told (`changed`),
 * lets the dialog's own closing pass through `wants`, and shows the question while `asking`. A
 * form that knows better than its events whether anything changed says so itself (`dirty`).
 */
export class CloseGuard {
	/** Whether something was typed into the form since the dialog opened. */
	touched = $state(false);
	/** Whether the question stands. */
	asking = $state(false);

	/** An `input` event of the form. Typing counts: a text is what cannot be chosen again in a
	 * moment. A search only narrows what the dialog shows, a tick or a choice is set again in a
	 * tap; neither asks. */
	changed = (event: Event): void => {
		const field = event.target;
		if (field instanceof HTMLTextAreaElement) this.touched = true;
		else if (field instanceof HTMLInputElement && TYPED.has(field.type)) this.touched = true;
	};

	/** The dialog opened: nothing is typed yet. */
	start(): void {
		this.touched = false;
		this.asking = false;
	}

	/** Whether the dialog may close now; if not, the question stands. */
	wants(dirty: boolean = this.touched): boolean {
		if (!dirty) return true;
		this.asking = true;
		return false;
	}
}

/** The kinds of `<input>` a person types into; not a search, not a tick, a file or a colour. */
const TYPED = new Set(['text', 'email', 'password', 'url', 'tel', 'number']);
