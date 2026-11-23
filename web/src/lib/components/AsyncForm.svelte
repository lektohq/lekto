<script lang="ts">
	import { tick, type Snippet } from 'svelte';
	import { describeError, FormIncomplete } from '#lib/errors.ts';

	// A form whose submit runs `action` (a request): busy meanwhile (a second submit does
	// nothing), `ondone` once it resolves (the dialog closes), the error described when it
	// throws. `children` get both, for the buttons and the error line. In a dialog the form is
	// made anew each time the dialog opens, so nothing is left over from the last time. The
	// dialog around it binds `busy`: while the action runs it does not close (web/DESIGN.md,
	// "Footers"), since the request goes on and takes effect all the same.
	let {
		action,
		ondone,
		busy = $bindable(false),
		class: className,
		onchanged,
		children
	}: {
		action: () => Promise<void>;
		ondone: () => void;
		/** The action runs. */
		busy?: boolean;
		class?: string;
		/** Something in the form was typed or chosen (for a question before leaving). */
		onchanged?: (event: Event) => void;
		children: Snippet<[{ busy: boolean; error: string | null }]>;
	} = $props();

	let error = $state<string | null>(null);
	let form = $state<HTMLFormElement | null>(null);

	// The first field marked as missing or wrong takes the focus.
	async function toFirstMarked() {
		await tick();
		const marked = form?.querySelector<HTMLElement>('[aria-invalid="true"]');
		const target = marked?.matches('input, select, textarea, button, [tabindex]')
			? marked
			: marked?.querySelector<HTMLElement>('input, select, textarea, button, [tabindex]');
		target?.focus();
	}

	async function submit(event: SubmitEvent) {
		event.preventDefault();
		if (busy) return;
		busy = true;
		error = null;
		try {
			await action();
			ondone();
		} catch (problem) {
			error = describeError(problem);
			if (problem instanceof FormIncomplete) void toFirstMarked();
		} finally {
			busy = false;
		}
	}
</script>

<form
	bind:this={form}
	class={className}
	onsubmit={submit}
	oninput={onchanged}
	onchange={onchanged}
	novalidate
>
	{@render children({ busy, error })}
</form>
