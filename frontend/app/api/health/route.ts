/**
 * Liveness probe for the web server itself (used by the container healthcheck).
 * Deliberately does not call the API: the web tier's health should not flap with it.
 */
export const dynamic = "force-dynamic";

export function GET(): Response {
  return Response.json({ status: "ok" });
}
