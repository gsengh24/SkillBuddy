/**
 * Security headers for every web page (next.config.ts). Kept here so they can be tested.
 *
 * The Content-Security-Policy allows only this site's own scripts, styles, fonts, images
 * and API calls (the browser talks only to our same-origin /api/v1 forwarder, and fonts are
 * self-hosted by next/font). Next.js needs inline scripts to start the page, hence
 * 'unsafe-inline' for scripts; development also needs 'unsafe-eval' and a WebSocket for
 * hot reload. Framing is refused twice: frame-ancestors and X-Frame-Options.
 * Strict-Transport-Security makes browsers use HTTPS only; it is sent in production (on
 * plain-HTTP localhost browsers ignore it anyway).
 */

export type Header = { key: string; value: string };

export function contentSecurityPolicy(isDev: boolean): string {
  const directives: Record<string, string[]> = {
    "default-src": ["'self'"],
    "script-src": ["'self'", "'unsafe-inline'", ...(isDev ? ["'unsafe-eval'"] : [])],
    "style-src": ["'self'", "'unsafe-inline'"],
    "img-src": ["'self'", "data:"],
    "font-src": ["'self'"],
    "connect-src": ["'self'", ...(isDev ? ["ws:", "wss:"] : [])],
    "frame-ancestors": ["'none'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'"],
    "object-src": ["'none'"],
  };
  return Object.entries(directives)
    .map(([name, values]) => `${name} ${values.join(" ")}`)
    .join("; ");
}

export function securityHeaders(isDev: boolean): Header[] {
  return [
    { key: "Content-Security-Policy", value: contentSecurityPolicy(isDev) },
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "X-Frame-Options", value: "DENY" },
    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
    { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
    ...(isDev
      ? []
      : [{ key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" }]),
  ];
}
