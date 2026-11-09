import { api } from '#lib/api/client.ts';
import { unwrap } from '#lib/api/call.ts';
import type { components } from '#lib/api/schema.ts';
import type { Contact, Tag } from '#lib/masterdata.svelte.ts';

export type Profile = components['schemas']['ProfileOut'];

/** What the API takes of a profile (`tests/api-limits.test.ts` holds them to `openapi.json`). */
export const PROFILE_LIMITS = { username: 150, displayName: 150, alias: 150, aliases: 10 } as const;

/** A user's profile with what their identifiers at contacts need: the contacts, whose topics
 * they may point to. */
export interface ProfileData {
	profile: Profile;
	contacts: Contact[];
	topics: Tag[];
}

/** The caller's own profile (`userId` null) or, for an admin, another user's. */
export async function loadProfile(userId: string | null): Promise<ProfileData> {
	const [profile, contacts, tags] = await Promise.all([
		unwrap(
			userId === null
				? api.GET('/api/v1/auth/me/profile')
				: api.GET('/api/v1/users/{id}/profile', { params: { path: { id: userId } } })
		),
		unwrap(api.GET('/api/v1/contacts')),
		unwrap(api.GET('/api/v1/tags'))
	]);
	return { profile, contacts, topics: tags.filter((tag) => tag.scope === 'topic') };
}

/** The tabs of the settings (Tobi, 02.11.2026); the first is shown without `?tab=` and for an
 * unknown one, the sign-in where linking an account came back with an error. */
export const SETTINGS_TABS = [
	'profile',
	'sign-in',
	'notifications',
	'tokens',
	'identifiers'
] as const;
export type SettingsTab = (typeof SETTINGS_TABS)[number];

export function settingsTab(params: Pick<URLSearchParams, 'get'>): SettingsTab {
	const tab = params.get('tab') ?? '';
	if ((SETTINGS_TABS as readonly string[]).includes(tab)) return tab as SettingsTab;
	return params.get('error') ? 'sign-in' : SETTINGS_TABS[0];
}
