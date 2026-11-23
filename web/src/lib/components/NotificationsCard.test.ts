import { render, screen, waitFor } from '@testing-library/svelte';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { m } from '#lib/paraglide/messages.js';
import { fakeApi } from '#lib/testing/api.ts';
import NotificationsCard from './NotificationsCard.svelte';

describe('NotificationsCard', () => {
	it('keeps the latest switch when an earlier answer comes last (WC-K03)', async () => {
		const user = userEvent.setup();
		let first: (() => void) | null = null;
		const sent: unknown[] = [];
		vi.stubGlobal(
			'fetch',
			fakeApi({
				'GET /api/v1/push': () => ({ enabled: true, public_key: 'key' }),
				'GET /api/v1/push/devices': () => [],
				'GET /api/v1/push/preferences': () => ({ kinds: [], titles: true }),
				'PUT /api/v1/push/preferences': async (request) => {
					const body = (await request.json()) as { kinds: string[]; titles: boolean };
					sent.push(body);
					if (sent.length === 1) await new Promise<void>((resolve) => (first = resolve));
					return body;
				}
			})
		);
		render(NotificationsCard);
		const waiting = await screen.findByRole('switch', { name: m.notifications_kind_waiting() });
		const disabled = screen.getByRole('switch', {
			name: m.notifications_kind_webhook_disabled()
		});
		await user.click(waiting);
		await waitFor(() => expect(sent).toHaveLength(1));
		await user.click(disabled);
		await waitFor(() => expect(sent).toHaveLength(2));
		first!();
		await new Promise((resolve) => setTimeout(resolve, 20));
		expect(disabled.getAttribute('aria-checked')).toBe('true');
		expect(waiting.getAttribute('aria-checked')).toBe('true');
	});
});
