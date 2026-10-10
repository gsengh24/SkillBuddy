import { describe, expect, it } from "vitest";

import nextConfig from "@/next.config";

import { contentSecurityPolicy, securityHeaders } from "./security-headers";

function asMap(headers: { key: string; value: string }[]) {
  return Object.fromEntries(headers.map(({ key, value }) => [key, value]));
}

describe("security headers", () => {
  it("in production: CSP, no framing, nosniff, referrer policy and HSTS", () => {
    const headers = asMap(securityHeaders(false));
    expect(headers["X-Content-Type-Options"]).toBe("nosniff");
    expect(headers["X-Frame-Options"]).toBe("DENY");
    expect(headers["Referrer-Policy"]).toBe("strict-origin-when-cross-origin");
    expect(headers["Strict-Transport-Security"]).toBe("max-age=63072000; includeSubDomains");
    const csp = headers["Content-Security-Policy"];
    expect(csp).toContain("default-src 'self'");
    expect(csp).toContain("frame-ancestors 'none'");
    expect(csp).toContain("object-src 'none'");
    expect(csp).toContain("connect-src 'self'");
    expect(csp).not.toContain("unsafe-eval");
    expect(csp).not.toContain("ws:");
  });

  it("loads images only from this site and Google's account-picture hosts", () => {
    const imgSrc = contentSecurityPolicy(false)
      .split("; ")
      .find((directive) => directive.startsWith("img-src "));
    expect(imgSrc).toBe(
      "img-src 'self' data: https://lh3.googleusercontent.com https://lh4.googleusercontent.com " +
        "https://lh5.googleusercontent.com https://lh6.googleusercontent.com",
    );
  });

  it("in development: hot reload allowed, no HSTS", () => {
    const headers = asMap(securityHeaders(true));
    expect(headers["Strict-Transport-Security"]).toBeUndefined();
    expect(contentSecurityPolicy(true)).toContain("'unsafe-eval'");
    expect(contentSecurityPolicy(true)).toContain("connect-src 'self' ws: wss:");
  });

  it("next.config applies them to every page", async () => {
    const rules = await nextConfig.headers!();
    expect(rules).toHaveLength(1);
    expect(rules[0]?.source).toBe("/:path*");
    const keys = rules[0]?.headers.map(({ key }) => key);
    expect(keys).toEqual(
      expect.arrayContaining([
        "Content-Security-Policy",
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
      ]),
    );
  });
});
