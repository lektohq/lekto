<script lang="ts">
	import { untrack } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api } from '#lib/api/client.ts';
	import { unwrap } from '#lib/api/call.ts';
	import type { components } from '#lib/api/schema.ts';
	import { BASE } from '#lib/base.ts';
	import RuleBuilder from '#lib/components/rules/RuleBuilder.svelte';
	import { Button } from '#lib/components/ui/button/index.ts';
	import { spaceOptions } from '#lib/masterdata.svelte.ts';
	import { masterDataDialogs } from '#lib/masterdata-dialog.svelte.ts';
	import { canChangeRule } from '#lib/permissions.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { RuleForm } from '#lib/rules/form.svelte.ts';
	import { fromApi, toApi, type RuleModel } from '#lib/rules/model.ts';
	import { RuleLoader } from '#lib/rules/page.svelte.ts';
	import { placeOf, rulePlaces } from '#lib/rules/places.ts';
	import { changeSwitchedOff } from '#lib/rules/save.ts';
	import { session } from '#lib/session.svelte.ts';
	import PageHeader from '#lib/components/page/PageHeader.svelte';
	import LoadProblem from '#lib/components/LoadProblem.svelte';
	import Loading from '#lib/components/Loading.svelte';
	import UnsavedGuard from '#lib/components/UnsavedGuard.svelte';

	type Rule = components['schemas']['RuleOut'];

	const id = $derived(page.params.id ?? '');
	let rule = $state<Rule | null>(null);
	let model = $state<RuleModel | null>(null);
	const loader = new RuleLoader();
	const lookup = $derived(loader.lookup);
	const problem = $derived(loader.problem);
	const form = new RuleForm();
	// Where the rule moves to (empty: where it is); its space changes with its content.
	let chosen = $state('');
	const current = $derived(rule ? placeOf(rule) : '');
	const place = $derived(chosen || current);
	const places = $derived(
		rulePlaces(
			lookup?.spaces ?? [],
			lookup?.users ?? [],
			session.user?.id,
			session.isAdmin,
			current
		)
	);

	// The rule files where whoever saves it may file (the API checks it for the caller).
	// Changed since it loaded, to ask before it is lost; cleared once saved or cancelled.
	let leaving = $state(false);
	const changed = $derived(
		rule !== null &&
			model !== null &&
			(place !== current || JSON.stringify(toApi(model)) !== JSON.stringify(toApi(fromApi(rule))))
	);

	const targets = $derived(spaceOptions(lookup?.spaces ?? [], lookup?.users ?? [], session.user));

	$effect(() => {
		const wanted = id;
		untrack(() =>
			loader.load(
				() => unwrap(api.GET('/api/v1/rules/{id}', { params: { path: { id: wanted } } })),
				(found, loaded) => {
					rule = found;
					// Only who may change the rule gets its editor (the API refuses the others when
					// they save); the page of the rule offers "Edit" by the same rule.
					if (!canChangeRule(found, session.user, loaded.spaces)) {
						model = null;
						loader.refuse(whyNot(found));
						return;
					}
					model = fromApi(found);
				}
			)
		);
	});

	/** Why the caller may not change `found`, as the API says it when one saves. */
	function whyNot(found: Rule): string {
		if (found.managed_by_document_type_id) return m.reason_rule_follows_type({ type: found.name });
		return found.scope === 'global'
			? `${m.error_forbidden()} ${m.reason_admins_only({ action: m.action_change_global_rules() })}`
			: m.error_forbidden();
	}

	async function save() {
		if (!rule || !model || !lookup || !form.check(model, lookup.fields)) return;
		const definition = toApi(model);
		const before = toApi(fromApi(rule));
		const moved = place !== current;
		if (!moved && JSON.stringify(definition) === JSON.stringify(before)) {
			leaving = true;
			await goto(`${BASE}/rules/${rule.id}`);
			return;
		}
		const target = rule;
		const saved = await form.save(model, () =>
			changeSwitchedOff(target, definition, moved ? place : undefined)
		);
		if (!saved) return;
		leaving = true;
		await goto(`${BASE}/rules/${saved.id}/apply?saved=1`);
	}
</script>

<svelte:head
	><title
		>{rule ? m.rule_edit_title({ name: rule.name }) : m.rule_edit_generic()} · {m.app_name()}</title
	></svelte:head
>

<UnsavedGuard dirty={changed && !leaving} />

<div class="flex flex-col gap-6">
	<PageHeader
		title={rule ? m.rule_edit_title({ name: rule.name }) : m.rule_edit_generic()}
		back={{
			href: rule ? `${BASE}/rules/${id}` : `${BASE}/rules`,
			label: rule?.name ?? m.nav_rules()
		}}
	/>

	{#if problem}
		<LoadProblem {problem} onretry={loader.onretry}>
			{#if rule?.managed_by_document_type_id && session.isAdmin}
				{@const type = rule.managed_by_document_type_id}
				<!-- The pattern is changed at its type: the way there. -->
				<Button
					variant="outline"
					onclick={() => masterDataDialogs.open('document-types', type, { fromRule: id })}
				>
					{m.rule_title_pattern_of({ type: rule.name })}
				</Button>
			{/if}
		</LoadProblem>
	{:else if !rule || !model || !lookup}
		<Loading />
	{:else}
		<RuleBuilder
			{model}
			{place}
			{places}
			onplace={(next) => (chosen = next)}
			placeHint={m.rule_scope_move_hint()}
			{lookup}
			{targets}
			errors={form.errors}
			general={form.general}
			busy={form.busy}
			cancelHref="{BASE}/rules/{rule.id}"
			oncancel={() => (leaving = true)}
			onsubmit={save}
		/>
	{/if}
</div>
