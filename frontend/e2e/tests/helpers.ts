import { expect, type APIRequestContext, type Page } from "@playwright/test";

const MAILPIT_URL = process.env.MAILPIT_URL ?? "http://localhost:8025";

/** The 6-digit code from the newest email to ``email`` in Mailpit. */
export async function codeFromMailpit(request: APIRequestContext, email: string): Promise<string> {
  let code: string | undefined;
  await expect
    .poll(
      async () => {
        const response = await request.get(`${MAILPIT_URL}/api/v1/search`, {
          params: { query: `to:"${email}"` },
        });
        const body = (await response.json()) as { messages?: { Snippet?: string }[] };
        code = body.messages?.[0]?.Snippet?.match(/\b(\d{6})\b/)?.[1];
        return code;
      },
      { message: `waiting for the sign-in email to ${email}`, timeout: 60_000 },
    )
    .toBeDefined();
  return code as string;
}

/** Creates an account through the real sign-in flow and lands on ``next``. */
export async function signUp(page: Page, request: APIRequestContext, next = "/home") {
  const email = `e2e-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  await page.goto(`/login?next=${encodeURIComponent(next)}`);
  await page.getByLabel("Email address").fill(email);
  await page.getByRole("checkbox", { name: /18 or older/ }).check();
  await page.getByRole("checkbox", { name: /accept the/ }).check();
  await page.getByRole("button", { name: "Email me a code" }).click();
  await expect(page.getByRole("heading", { name: "Check your email" })).toBeVisible();
  await page.getByLabel("Sign-in code").fill(await codeFromMailpit(request, email));
  await page.getByRole("button", { name: "Sign in" }).click();
  return email;
}

/**
 * Waits until one-off animations (fade-ups, the hero cells) have finished, so checks such as
 * axe's colour contrast measure what people see, not a half-faded frame. Endless animations
 * (the loading pulse) are not waited for.
 */
export async function settleAnimations(page: Page) {
  await page.evaluate(() =>
    Promise.all(
      document
        .getAnimations()
        .filter((animation) => animation.effect?.getTiming().iterations !== Infinity)
        .map((animation) => animation.finished.catch(() => undefined)),
    ),
  );
}
