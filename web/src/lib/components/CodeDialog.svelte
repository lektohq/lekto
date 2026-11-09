<script lang="ts" module>
	/** The longest code the API takes (`CodeIn`, `tests/api-limits.test.ts`). */
	export const CODE_MAX = 64;
</script>

<script lang="ts">
	import FormDialog from '#lib/components/FormDialog.svelte';
	import * as Field from '#lib/components/ui/field/index.ts';
	import { Input } from '#lib/components/ui/input/index.ts';
	import { m } from '#lib/paraglide/messages.js';

	// A dialog that asks for one code from the authenticator (or a recovery code). The API decides
	// whether it is right; its answer shows under the field.
	let {
		open = $bindable(false),
		title,
		description,
		submitLabel,
		destructive = false,
		onsubmit
	}: {
		open?: boolean;
		title: string;
		description: string;
		submitLabel: string;
		destructive?: boolean;
		onsubmit: (code: string) => Promise<void>;
	} = $props();

	let code = $state('');

	$effect(() => {
		if (open) code = '';
	});
</script>

<FormDialog
	bind:open
	{title}
	{description}
	{submitLabel}
	{destructive}
	disabled={code.trim() === ''}
	action={() => onsubmit(code.replace(/\s+/g, ''))}
>
	{#snippet children(error)}
		<Field.Field>
			<Field.Label for="code-dialog-input">{m.totp_code()}</Field.Label>
			<Input
				id="code-dialog-input"
				bind:value={code}
				inputmode="numeric"
				autocomplete="one-time-code"
				maxlength={CODE_MAX}
				required
				aria-invalid={error ? true : undefined}
			/>
		</Field.Field>
	{/snippet}
</FormDialog>
