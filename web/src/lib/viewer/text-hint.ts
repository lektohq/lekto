/**
 * Where the text of the pages is. The pages a viewer shows are images of the person's documents:
 * a screen reader gets their names ("Seite 1 von 3") and, from whoever shows the viewer, a
 * sentence on where the text of those pages stands (WCAG 1.1.1). The document view offers it
 * under "Text"; the Beam only shows, and points there. Set as a context around the viewer.
 */
export const TEXT_HINT = Symbol('where the text of the pages is');

/** The sentence, or null where there is no text to point at (the pages of a stack being cut). */
export type TextHint = () => string | null;
