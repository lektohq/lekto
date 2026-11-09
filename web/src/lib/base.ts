import { BASE_API } from '#lib/api/base.ts';

/** Where the app lives on the server; the API stays below `/api/v1`. */
export const BASE = '/ui';

/** The Swagger UI of the REST API, served by the API itself. */
export const API_DOCS = `${BASE_API}/docs`;
