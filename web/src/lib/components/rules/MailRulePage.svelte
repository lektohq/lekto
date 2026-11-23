<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { api } from '#lib/api/client.ts';
	import { unwrap } from '#lib/api/call.ts';
	import { BASE } from '#lib/base.ts';
	import LoadProblem from '#lib/components/LoadProblem.svelte';
	import Loading from '#lib/components/Loading.svelte';
	import PageHeader from '#lib/components/page/PageHeader.svelte';
	import MailRuleForm from '#lib/components/rules/MailRuleForm.svelte';
	import UnsavedGuard from '#lib/components/UnsavedGuard.svelte';
	import { describeLoad, type LoadFailure } from '#lib/errors.ts';
	import { loadMailRuleLookup, type MailRuleLookup } from '#lib/mail-rule-lookup.ts';
	import {
		createBody,
		formOf,
		mailRulePlaces,
		patchBody,
		validate,
		type MailRule,
		type MailRuleForm as Form
	} from '#lib/mail-rules.ts';
	import { m } from '#lib/paraglide/messages.js';
	import { saveErrorsAt } from '#lib/rules/errors.ts';
	import { RuleForm } from '#lib/rules/form.svelte.ts';

	// The editor of a mail rule (Tobi, 04./05.11.2026; mock E), as the document rules': a new
	// one (`id` null; the mailbox from `?mailbox=`, its type of the mail text proposed) or a
	// stored one. It is saved switched off, in one request, and the dry run follows: the person
	// sees what it would do before switching it on (as `rules/save.ts` does). Checking and
	// saving go the way of every rule (`RuleForm`): a refused save stands next to the field,
	// the condition or the step the API names.
	let { id }: { id: string | null } = $props();

	let rule = $state<MailRule | null>(null);
	let form = $state<Form | null>(null);
	let initial = '';
	let lookup = $state<MailRuleLookup | null>(null);
	let failure = $state<LoadFailure | null>(null);
	const saving = new RuleForm();
	let leaving = $state(false);

	const changed = $derived(form !== null && JSON.stringify(form) !== initial);
	// To the rule, or to the list where there is none (a new one, one that is not there).
	const back = $derived(
		id && !failure?.final ? `${BASE}/rules/mail/${id}` : `${BASE}/rules?kind=mail`
	);

	async function load() {
		failure = null;
		try {
			const [loaded, stored] = await Promise.all([
				loadMailRuleLookup(),
				id ? unwrap(api.GET('/api/v1/mail-rules/{id}', { params: { path: { id } } })) : null
			]);
			[lookup, rule] = [loaded, stored];
			const wanted = page.url.searchParams.get('mailbox');
			const mailbox = loaded.mailboxes.find((entry) => entry.id === wanted) ?? loaded.mailboxes[0];
			form = formOf(stored, mailbox?.id ?? '', mailbox?.body_type_id ?? '');
			initial = JSON.stringify(form);
		} catch (error) {
			failure = describeLoad(error, m.mail_rule_not_found);
		}
	}

	onMount(load);

	async function save() {
		const held = form;
		if (!held || !saving.show(validate(held, lookup?.spaces ?? []))) return;
		const saved = await saving.saveAt(
			() =>
				id
					? unwrap(
							api.PATCH('/api/v1/mail-rules/{id}', {
								params: { path: { id } },
								body: { ...patchBody(held), enabled: false }
							})
						)
					: unwrap(
							api.POST('/api/v1/mail-rules', { body: { ...createBody(held), enabled: false } })
						),
			(error) => saveErrorsAt(error, mailRulePlaces(held))
		);
		if (!saved) return;
		leaving = true;
		await goto(`${BASE}/rules/mail/${saved.id}/apply?saved=1`);
	}

	const title = $derived(
		id ? m.rule_edit_title({ name: rule?.name ?? m.mail_rule_generic() }) : m.mail_rule_new_title()
	);
</script>

<svelte:head><title>{title} · {m.nav_rules()} · {m.app_name()}</title></svelte:head>

<UnsavedGuard dirty={changed && !leaving} />

<div class="flex flex-col gap-6">
	<PageHeader
		{title}
		back={{ href: back, label: id ? (rule?.name ?? m.nav_rules()) : m.nav_rules() }}
	/>

	{#if failure}
		<LoadProblem problem={failure.text} onretry={failure.final ? undefined : load} />
	{:else if !form || !lookup}
		<Loading />
	{:else}
		<MailRuleForm
			{form}
			mailboxes={lookup.mailboxes}
			users={lookup.users}
			spaces={lookup.spaces}
			types={lookup.types}
			errors={saving.errors}
			busy={saving.busy}
			error={saving.general}
			cancelHref={back}
			oncancel={() => (leaving = true)}
			onsubmit={save}
		/>
	{/if}
</div>
