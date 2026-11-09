<script lang="ts">
	import { Switch } from '#lib/components/ui/switch/index.ts';
	import { m } from '#lib/paraglide/messages.js';

	// The switch of a rule, document or mail rule alike (web/DESIGN.md, "Mail rules"): named by
	// what it does to the rule. The caller changes the rule (`lib/rules/switch.ts`).
	let {
		name,
		enabled,
		busy = false,
		onswitch,
		class: className
	}: {
		name: string;
		enabled: boolean;
		busy?: boolean;
		onswitch: (enabled: boolean) => void;
		class?: string;
	} = $props();
</script>

<Switch
	bind:checked={() => enabled, onswitch}
	disabled={busy}
	class={className}
	aria-label={enabled ? m.rule_switch_off({ name }) : m.rule_switch_on({ name })}
/>
