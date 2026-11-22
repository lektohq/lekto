import type { components } from '#lib/api/schema.ts';
import { reasonsText } from '#lib/reasons.ts';

type Preview = components['schemas']['TemplatePreviewOut'];

/**
 * Why a template is invalid, as the preview says it: in the user's language where the reason
 * has a code (a value templates do not know), else the words of the template engine, which
 * the API gives as text.
 */
export function previewError(preview: Pick<Preview, 'error' | 'error_reason'>): string | null {
	if (!preview.error) return null;
	return preview.error_reason ? reasonsText([preview.error_reason], preview.error) : preview.error;
}
