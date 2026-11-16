import type { RequestHandler } from './$types';

export const GET: RequestHandler = () => {
  // Lightweight liveness probe for the frontend container.
  return Response.json({ status: 'ok' }, { status: 200 });
};
