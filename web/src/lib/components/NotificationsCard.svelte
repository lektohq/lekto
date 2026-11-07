<script lang="ts">
	import Check from '@lucide/svelte/icons/check';
	import Trash from '@lucide/svelte/icons/trash-2';
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { api } from '#lib/api/client.ts';
	import { unwrap } from '#lib/api/call.ts';
	import type { components } from '#lib/api/schema.ts';
	import ConfirmDialog from '#lib/components/ConfirmDialog.svelte';
	import IconButton from '#lib/components/IconButton.svelte';
	import Loading from '#lib/components/Loading.svelte';
	import LoadProblem from '#lib/components/LoadProblem.svelte';
	import * as Alert from '#lib/components/ui/alert/index.ts';
	import { Badge } from '#lib/components/ui/badge/index.ts';
	import { Button } from '#lib/components/ui/button/index.ts';
	import * as Card from '#lib/components/ui/card/index.ts';
	import { Switch } from '#lib/components/ui/switch/index.ts';
	import { describeError, reportError } from '#lib/errors.ts';
	import { formatDate, getLocale } from '#lib/i18n.ts';
	import { m } from '#lib/paraglide/messages.js';
	import {
		currentSubscription,
		deviceName,
		pushSupport,
		subscribe,
		unblockSteps,
		type UnblockStep
	} from '#lib/push-device.ts';
	import { session } from '#lib/session.svelte.ts';

	// Settings › Benachrichtigungen (web/DESIGN.md, "App"): this device (switch on, test, switch
	// off; on an iPhone in Safari the way into the app instead), what the person is told about,
	// whether titles show on a locked screen, and their devices.
	type Device = components['schemas']['PushDeviceOut'];
	type Kind = components['schemas']['PushPreferencesBody']['kinds'][number];

	const support = pushSupport();
	let enabled = $state<boolean | null>(null);
	let publicKey = $state<string | null>(null);
	let devices = $state<Device[] | null>(null);
	let kinds = $state<Kind[]>([]);
	let titles = $state(true);
	let endpoint = $state<string | null>(null);
	let problem = $state<string | null>(null);
	let busy = $state(false);
	let blocked = $state(support === 'ready' && Notification.permission === 'denied');
	let removing = $state<Device | null>(null);

	const here = $derived(devices?.find((device) => device.endpoint === endpoint) ?? null);
	const KINDS: { kind: Kind; label: () => string; admin: boolean }[] = [
		{ kind: 'waiting', label: m.notifications_kind_waiting, admin: false },
		{ kind: 'webhook_disabled', label: m.notifications_kind_webhook_disabled, admin: false },
		{ kind: 'mailbox_failed', label: m.notifications_kind_mailbox_failed, admin: true },
		{ kind: 'job_failed', label: m.notifications_kind_job_failed, admin: true }
	];
	const shown = $derived(KINDS.filter((item) => !item.admin || session.isAdmin));
	// Where to allow them again, for this browser (a Dock app has settings of its own).
	const UNBLOCK: Record<UnblockStep, () => string> = {
		'dock-app': m.notifications_unblock_dock_app,
		safari: m.notifications_unblock_safari,
		'address-bar': m.notifications_unblock_address_bar,
		macos: m.notifications_unblock_macos
	};
	const unblock = support === 'ready' ? unblockSteps() : [];

	async function load() {
		problem = null;
		try {
			const [settings, list, preferences] = await Promise.all([
				unwrap(api.GET('/api/v1/push')),
				unwrap(api.GET('/api/v1/push/devices')),
				unwrap(api.GET('/api/v1/push/preferences'))
			]);
			enabled = settings.enabled;
			publicKey = settings.public_key;
			devices = list;
			kinds = preferences.kinds;
			titles = preferences.titles;
			endpoint = support === 'ready' ? ((await currentSubscription())?.endpoint ?? null) : null;
		} catch (failure) {
			problem = describeError(failure);
		}
	}

	onMount(load);

	async function switchOn() {
		if (busy || !publicKey) return;
		busy = true;
		try {
			const subscription = await subscribe(publicKey);
			if (subscription === 'denied') {
				blocked = true;
				return;
			}
			if (subscription === 'unavailable') {
				toast.error(m.notifications_unsupported());
				return;
			}
			const keys = subscription.toJSON().keys ?? {};
			await unwrap(
				api.POST('/api/v1/push/devices', {
					body: {
						endpoint: subscription.endpoint,
						keys: { p256dh: keys.p256dh ?? '', auth: keys.auth ?? '' },
						name: deviceName(),
						locale: getLocale() === 'de' ? 'de' : 'en'
					}
				})
			);
			await load();
		} catch (failure) {
			reportError(failure);
		} finally {
			busy = false;
		}
	}

	async function switchOff() {
		if (!here) return;
		removing = here;
	}

	async function remove() {
		const device = removing;
		if (!device) return;
		await unwrap(api.DELETE('/api/v1/push/devices/{id}', { params: { path: { id: device.id } } }));
		if (device.endpoint === endpoint) await (await currentSubscription())?.unsubscribe();
		await load();
	}

	async function test() {
		if (!here || busy) return;
		busy = true;
		try {
			const result = await unwrap(
				api.POST('/api/v1/push/devices/{id}/test', { params: { path: { id: here.id } } })
			);
			if (result.outcome === 'delivered') toast.success(m.notifications_test_sent());
			else if (result.outcome === 'gone') {
				toast.error(m.notifications_test_gone());
				await load();
			} else toast.error(m.notifications_test_failed());
		} catch (failure) {
			reportError(failure);
		} finally {
			busy = false;
		}
	}

	// A switch takes effect at once (web/DESIGN.md, "Saving and leaving").
	async function save(nextKinds: Kind[], nextTitles: boolean) {
		const before = { kinds, titles };
		kinds = nextKinds;
		titles = nextTitles;
		try {
			const saved = await unwrap(
				api.PUT('/api/v1/push/preferences', { body: { kinds: nextKinds, titles: nextTitles } })
			);
			kinds = saved.kinds;
			titles = saved.titles;
		} catch (failure) {
			({ kinds, titles } = before);
			reportError(failure);
		}
	}

	function toggle(kind: Kind, on: boolean) {
		void save(on ? [...new Set([...kinds, kind])] : kinds.filter((item) => item !== kind), titles);
	}
</script>

{#if problem}
	<LoadProblem {problem} onretry={load} />
{:else if enabled === null || devices === null}
	<Loading />
{:else}
	<Card.Root>
		<Card.Header>
			<Card.Title class="flex flex-wrap items-center gap-2">
				{m.notifications_device()}
				{#if here}
					<Badge variant="green"><Check aria-hidden="true" />{m.notifications_device_on()}</Badge>
				{/if}
			</Card.Title>
			{#if here}<Card.Description>{here.name}</Card.Description>{/if}
		</Card.Header>
		<Card.Content class="flex flex-col gap-3">
			{#if !enabled}
				<p class="text-muted-foreground">{m.notifications_off_server()}</p>
			{:else if support === 'install-first'}
				<Alert.Root variant="tip">
					<Alert.Title>{m.notifications_install_title()}</Alert.Title>
					<Alert.Description>
						<ol class="list-decimal pl-5">
							<li>{m.notifications_step_share()}</li>
							<li>{m.notifications_step_home()}</li>
							<li>{m.notifications_step_open()}</li>
						</ol>
					</Alert.Description>
				</Alert.Root>
			{:else if support === 'unsupported'}
				<p class="text-muted-foreground">{m.notifications_unsupported()}</p>
			{:else if here}
				<div class="flex flex-wrap gap-2">
					<Button variant="outline" aria-disabled={busy} onclick={test}>
						{m.notifications_test()}
					</Button>
					<Button variant="ghost" onclick={switchOff}>{m.notifications_switch_off()}</Button>
				</div>
			{:else if blocked}
				<Alert.Root variant="warning">
					<Alert.Title>{m.notifications_blocked()}</Alert.Title>
					<Alert.Description>
						<ol class="list-decimal pl-5">
							{#each unblock as step (step)}<li>{UNBLOCK[step]()}</li>{/each}
							<li>{m.notifications_unblock_reload()}</li>
						</ol>
					</Alert.Description>
				</Alert.Root>
			{:else}
				<Button class="self-start" aria-disabled={busy} onclick={switchOn}>
					{m.notifications_switch_on()}
				</Button>
			{/if}
		</Card.Content>
	</Card.Root>

	<Card.Root>
		<Card.Header><Card.Title>{m.notifications_when()}</Card.Title></Card.Header>
		<Card.Content>
			<ul class="divide-y">
				{#each shown as item (item.kind)}
					<li class="flex min-h-11 items-center justify-between gap-3 py-2">
						<span>{item.label()}</span>
						<Switch
							checked={kinds.includes(item.kind)}
							onCheckedChange={(on) => toggle(item.kind, on)}
							aria-label={item.label()}
						/>
					</li>
				{/each}
			</ul>
		</Card.Content>
	</Card.Root>

	<Card.Root>
		<Card.Header><Card.Title>{m.notifications_lock_screen()}</Card.Title></Card.Header>
		<Card.Content>
			<div class="flex min-h-11 items-center justify-between gap-3">
				<div class="flex flex-col">
					<span>{m.notifications_titles()}</span>
					<span class="text-sm text-muted-foreground">{m.notifications_titles_hint()}</span>
				</div>
				<Switch
					checked={titles}
					onCheckedChange={(on) => void save(kinds, on)}
					aria-label={m.notifications_titles()}
				/>
			</div>
		</Card.Content>
	</Card.Root>

	<Card.Root>
		<Card.Header><Card.Title>{m.notifications_devices()}</Card.Title></Card.Header>
		<Card.Content>
			{#if devices.length === 0}
				<p class="text-muted-foreground">{m.notifications_none()}</p>
			{:else}
				<ul class="divide-y">
					{#each devices as device (device.id)}
						<li class="flex items-center gap-3 py-3">
							<div class="min-w-0 flex-1">
								<p class="truncate font-medium">{device.name}</p>
								<p class="text-sm text-muted-foreground">
									{[
										device.endpoint === endpoint ? m.notifications_this_device() : null,
										device.last_success_at
											? m.notifications_last({
													time: formatDate(device.last_success_at, {
														dateStyle: 'short',
														timeStyle: 'short'
													})
												})
											: m.notifications_never()
									]
										.filter(Boolean)
										.join(' · ')}
								</p>
							</div>
							<IconButton
								label={m.notifications_remove_named({ name: device.name })}
								onclick={() => (removing = device)}
							>
								<Trash aria-hidden="true" />
							</IconButton>
						</li>
					{/each}
				</ul>
			{/if}
		</Card.Content>
	</Card.Root>
{/if}

<ConfirmDialog
	bind:open={() => removing !== null, (open) => !open && (removing = null)}
	title={m.notifications_remove_named({ name: removing?.name ?? '' })}
	description={m.notifications_remove_confirm()}
	confirmLabel={m.notifications_remove()}
	onconfirm={remove}
/>
