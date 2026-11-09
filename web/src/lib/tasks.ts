/**
 * A task a webhook answers (the rule action "ask a webhook", a model call): how long it may
 * take, in seconds, as the API takes it (`tests/api-limits.test.ts`).
 */
export const TIMEOUT = { min: 30, max: 86_400, default: 300 } as const;

/** The time to answer in the minutes a form shows. */
export const TIMEOUT_MINUTES = {
	min: TIMEOUT.min / 60,
	max: TIMEOUT.max / 60,
	default: TIMEOUT.default / 60
} as const;
