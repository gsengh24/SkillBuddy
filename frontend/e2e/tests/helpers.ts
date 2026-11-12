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

/** The first link in the newest email to ``email`` whose subject contains ``subject``. */
export async function linkFromMailpit(
  request: APIRequestContext,
  email: string,
  subject: string,
): Promise<string> {
  let link: string | undefined;
  await expect
    .poll(
      async () => {
        const response = await request.get(`${MAILPIT_URL}/api/v1/search`, {
          params: { query: `to:"${email}" subject:"${subject}"` },
        });
        const body = (await response.json()) as { messages?: { ID: string }[] };
        const id = body.messages?.[0]?.ID;
        if (!id) return undefined;
        const message = (await (
          await request.get(`${MAILPIT_URL}/api/v1/message/${id}`)
        ).json()) as { Text?: string };
        link = message.Text?.match(/https?:\/\/\S+/)?.[0];
        return link;
      },
      { message: `waiting for the "${subject}" email to ${email}`, timeout: 90_000 },
    )
    .toBeDefined();
  return link as string;
}

/**
 * Creates an account through the real sign-in flow and goes to ``next``. A new account has
 * onboarding to do, so a plain ``/home`` sends it on to step 1 (ADR 0022, P7).
 */
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

/**
 * Goes through onboarding (ADR 0022) from step 1 and confirms the card on step 5, landing
 * on Home. The CI stack has no AI keys, so the card is the template version.
 */
export async function onboard(
  page: Page,
  {
    name,
    offers = ["React", "Python"],
    wants = ["Figma"],
    interests = ["Chess"],
  }: { name: string; offers?: string[]; wants?: string[]; interests?: string[] },
) {
  await page.goto("/onboarding");
  await page.getByRole("button", { name: /Build together/ }).click();
  await page.getByRole("button", { name: /Continue/ }).click();
  await expect(page.getByRole("heading", { level: 1, name: /What are you good at/ })).toBeVisible();
  for (const skill of offers) {
    await page.getByRole("button", { name: skill, exact: true }).first().click();
  }
  await page.getByRole("button", { name: /Continue/ }).click();
  await expect(
    page.getByRole("heading", { level: 1, name: /What are you looking for/ }),
  ).toBeVisible();
  for (const tag of [...wants, ...interests]) {
    await page.getByRole("button", { name: tag, exact: true }).first().click();
  }
  await page.getByRole("button", { name: /Continue/ }).click();
  await expect(page.getByRole("heading", { level: 1, name: /Almost done/ })).toBeVisible();
  await page.getByRole("radio", { name: "2nd" }).click();
  await page.getByRole("button", { name: "Saturday" }).click();
  await page.getByLabel("Display name").fill(name);
  await page.getByRole("checkbox", { name: /read by AI to find and explain/ }).check();
  await page.getByRole("button", { name: /Finish/ }).click();
  await expect(page).toHaveURL(/\/onboarding\/review$/);
  await expect(page.getByRole("article", { name: "Preview of your match card" })).toBeVisible({
    timeout: 30_000,
  });
  await page.getByRole("button", { name: /Looks good/ }).click();
  await expect(page).toHaveURL(/\/home/);
}
