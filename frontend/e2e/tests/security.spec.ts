import { expect, test } from "@playwright/test";

import { signUp } from "./helpers";

/**
 * Security headers are sent on real pages, and the Content-Security-Policy doesn't break
 * them: any CSP violation reported by the browser fails the test. (HSTS is sent only in
 * production builds over HTTPS, so it is checked only when the base URL is https.)
 */
test("web pages send the security headers and break no CSP rule", async ({ page, request }) => {
  const violations: string[] = [];
  page.on("console", (message) => {
    if (/Content Security Policy/i.test(message.text())) violations.push(message.text());
  });

  const response = await page.goto("/login");
  const headers = response?.headers() ?? {};
  expect(headers["content-security-policy"]).toContain("default-src 'self'");
  expect(headers["content-security-policy"]).toContain("frame-ancestors 'none'");
  expect(headers["x-content-type-options"]).toBe("nosniff");
  expect(headers["x-frame-options"]).toBe("DENY");
  expect(headers["referrer-policy"]).toBe("strict-origin-when-cross-origin");
  if (page.url().startsWith("https://")) {
    expect(headers["strict-transport-security"]).toContain("max-age=");
  }
  await expect(page.getByRole("heading", { name: /Sign in/, level: 1 })).toBeVisible();

  // A signed-in page, with its client-side code and API calls, under the same policy.
  await signUp(page, request, "/messages");
  await expect(page.getByRole("heading", { name: "Messages", level: 1 })).toBeVisible();
  await page.goto("/privacy");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

  expect(violations).toEqual([]);
});
