/**
 * The tones of the UI (web/DESIGN.md, "Colour roles"): the lanes, what is still running, notes,
 * muted facts and the accent for what runs now. The one map from a tone to its classes:
 * components take a tone and never write the classes themselves. A mark of a tone has its
 * ground, its text in the tone's text colour and an edge in that colour; in the light theme
 * there are no dark fills.
 */
export type Tone = 'green' | 'yellow' | 'red' | 'running' | 'muted' | 'note' | 'primary';

/** The three lanes of a document. */
export type Lane = 'green' | 'yellow' | 'red';

/** Ground and text of a tone. */
export const TONE_FILL: Record<Tone, string> = {
	green: 'bg-lane-green text-lane-green-foreground',
	yellow: 'bg-lane-yellow text-lane-yellow-foreground',
	red: 'bg-lane-red text-lane-red-foreground',
	running: 'bg-lane-running text-lane-running-foreground',
	muted: 'bg-muted text-muted-foreground',
	note: 'bg-note text-note-foreground',
	primary: 'bg-primary/10 text-brand'
};

/** The edge of a tone's mark, in its text colour, so a pale ground stands off the card. */
export const TONE_EDGE: Record<Tone, string> = {
	green: 'border-lane-green-foreground/30',
	yellow: 'border-lane-yellow-foreground/35',
	red: 'border-lane-red-foreground/30',
	running: 'border-lane-running-foreground/25',
	muted: 'border-transparent',
	note: 'border-note-foreground/25',
	primary: 'border-primary/30'
};

/** A lane as a mark that carries no text (a step of the processing band, the rail of the
 * timeline, a bar): the lane's ground with the edge of its chip, drawn inside (a ring), so the
 * mark keeps its size. */
export const LANE_MARK: Record<Lane, string> = {
	green: 'bg-lane-green ring-1 ring-inset ring-lane-green-foreground/30',
	yellow: 'bg-lane-yellow ring-1 ring-inset ring-lane-yellow-foreground/35',
	red: 'bg-lane-red ring-1 ring-inset ring-lane-red-foreground/30'
};

/** A small mark (a dot of the timeline, the counts, the matrix): flat, the tone's ground in a
 * full edge of its text colour, 1.5 px wide (`border-dot`; web/DESIGN.md, "Colour roles"). A
 * faint edge or an inner ring looks shaded at that size. */
export const TONE_DOT: Record<Tone, string> = {
	green: 'border-dot border-lane-green-foreground bg-lane-green',
	yellow: 'border-dot border-lane-yellow-foreground bg-lane-yellow',
	red: 'border-dot border-lane-red-foreground bg-lane-red',
	running: 'border-dot border-lane-running-foreground bg-lane-running',
	muted: 'border-dot border-border bg-muted',
	note: 'border-dot border-note-foreground bg-note',
	primary: 'border-dot border-primary bg-primary/10'
};

/** A stripe too thin for a ground (the steps beside the longest one in the band): the lane's
 * text colour, softened. */
export const LANE_STRIPE: Record<Lane, string> = {
	green: 'bg-lane-green-foreground/45',
	yellow: 'bg-lane-yellow-foreground/60',
	red: 'bg-lane-red-foreground/55'
};

/** Text in a tone's colour. */
export const TONE_TEXT: Record<Tone, string> = {
	green: 'text-lane-green-foreground',
	yellow: 'text-lane-yellow-foreground',
	red: 'text-lane-red-foreground',
	running: 'text-lane-running-foreground',
	muted: 'text-muted-foreground',
	note: 'text-note-foreground',
	primary: 'text-brand'
};

/** The edge of a step's card or of its details in the processing view, by the step's tone
 * (`step-look.ts`): quiet, or the lane's. */
export const STEP_BORDER: Record<StepTone, string> = {
	green: 'border-border',
	running: 'border-border',
	muted: 'border-border',
	yellow: 'border-lane-yellow-foreground/35',
	red: 'border-lane-red-foreground/35'
};

/** Their ground by the step's tone. */
export const STEP_TINT: Record<StepTone, string> = {
	green: 'bg-secondary/40',
	running: 'bg-secondary/40',
	muted: 'bg-secondary/40',
	yellow: 'bg-lane-yellow/60',
	red: 'bg-lane-red/60'
};

/** The tones a step of the processing can have. */
type StepTone = Extract<Tone, 'green' | 'yellow' | 'red' | 'running' | 'muted'>;

/** A lane's tone; a document without a lane is still being processed. */
export function laneTone(lane: Lane | null | undefined): Tone {
	return lane ?? 'running';
}
