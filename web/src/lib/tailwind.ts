/**
 * Class merging that knows the type scale of web/DESIGN.md. tailwind-merge takes `text-meta`,
 * `text-md`, `text-title` and the other steps defined in `app.css` for colours unless told they
 * are font sizes: a button of size `sm` (`text-meta`) then lost its variant's text colour
 * (`text-primary-foreground`), and a primary button wrote dark on petrol.
 */
import { extendTailwindMerge } from 'tailwind-merge';
import { createTV } from 'tailwind-variants';

/** The steps of the type scale beyond Tailwind's own (`--text-*` in `app.css`). */
export const TEXT_STEPS = ['nano', 'micro', 'meta', 'md', 'figure', 'title'];

/** The widths of a border beyond Tailwind's own (`@utility border-*` in `app.css`): `border-dot`
 * is the edge of a small mark, which tailwind-merge takes for a colour otherwise and drops
 * before the mark's own colour. */
export const BORDER_WIDTHS = ['dot'];

const config = {
	extend: {
		theme: { text: TEXT_STEPS },
		classGroups: { 'border-w': [{ border: BORDER_WIDTHS }] }
	}
};

export const twMerge = extendTailwindMerge(config);
export const tv = createTV({ twMergeConfig: config });
