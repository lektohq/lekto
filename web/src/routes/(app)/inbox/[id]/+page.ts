import { redirect } from '@sveltejs/kit';
import { documentHref } from '#lib/candidates.ts';
import type { PageLoad } from './$types';

// The inbox opens a document in the document view, which keeps its place among the inbox's.
export const load: PageLoad = ({ params }) => {
	redirect(307, `${documentHref(params.id)}?from=inbox`);
};
