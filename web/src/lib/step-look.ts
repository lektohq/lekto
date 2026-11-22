/**
 * How a step's state looks in the processing view: icon, label and tone (a lane colour, or
 * running, or muted). A lane is never told by colour alone: the icon and the label carry it.
 */
import Circle from '@lucide/svelte/icons/circle';
import CircleCheck from '@lucide/svelte/icons/circle-check';
import CircleDashed from '@lucide/svelte/icons/circle-dashed';
import Hourglass from '@lucide/svelte/icons/hourglass';
import LoaderCircle from '@lucide/svelte/icons/loader-circle';
import OctagonX from '@lucide/svelte/icons/octagon-x';
import TriangleAlert from '@lucide/svelte/icons/triangle-alert';
import { m } from '#lib/paraglide/messages.js';
import type { NodeState } from '#lib/pipeline.ts';
import type { Tone as UiTone } from '#lib/tones.ts';

/** The tones a step can have, of the UI's (`tones.ts`, which draws them). */
export type Tone = Extract<UiTone, 'green' | 'yellow' | 'red' | 'running' | 'muted'>;

export interface Look {
	icon: typeof Circle;
	label: string;
	tone: Tone;
	spin: boolean;
}

/** The look of a step in its state; null: it did not run in the run shown. */
export function stepLook(state: NodeState | null): Look {
	if (state === null) return { icon: Circle, label: m.log_not_run(), tone: 'muted', spin: false };
	if (state.status === 'running')
		return { icon: LoaderCircle, label: m.node_status_running(), tone: 'running', spin: true };
	if (state.status === 'delegated')
		return { icon: Hourglass, label: delegatedLabel(state), tone: 'running', spin: false };
	if (state.status === 'skipped')
		return { icon: CircleDashed, label: m.node_status_skipped(), tone: 'muted', spin: false };
	if (state.status === 'waiting')
		return { icon: Circle, label: m.node_status_waiting(), tone: 'muted', spin: false };
	if (state.outcome === 'failed')
		return { icon: OctagonX, label: m.outcome_failed(), tone: 'red', spin: false };
	if (state.outcome === 'uncertain')
		return { icon: TriangleAlert, label: m.outcome_uncertain(), tone: 'yellow', spin: false };
	return { icon: CircleCheck, label: m.outcome_ok(), tone: 'green', spin: false };
}

/** A node that waits for the answers to its tasks: running externally, with the minutes left
 * until the last of them ends (none while they wait to be sent). */
export function delegatedLabel(state: NodeState, now: Date = new Date()): string {
	if (state.deadline === null || state.deadline === undefined) return m.node_status_delegated();
	const left = (new Date(state.deadline).getTime() - now.getTime()) / 60_000;
	return m.node_status_delegated_left({ minutes: String(Math.max(1, Math.ceil(left))) });
}
