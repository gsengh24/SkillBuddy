import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

/**
 * "Continue with Google" end to end against the fake OpenID Connect provider that the CI
 * stack runs instead of Google (backend/tests/fake_oidc.py, ADR 0011). Its sign-in page
 * accepts whatever email is typed; the API must still refuse anything but @thapar.edu.
 */

async function startGoogle(page: Page, email: string) {
  await page.goto("/login");
  await page.getByRole("checkbox", { name: /18 or older/ }).check();
  await page.getByRole("checkbox", { name: /accept the/ }).check();
  await page.getByRole("button", { name: "Continue with Google" }).click();
  // The fake provider's account chooser.
  await expect(page.getByRole("heading", { name: "Fake Google sign-in" })).toBeVisible();
  await page.getByLabel("Email").fill(email);
  await page.getByRole("button", { name: "Continue" }).click();
}

test("the sign-in page offers Google first, with no accessibility violations", async ({ page }) => {
  await page.goto("/login");
  const google = page.getByRole("button", { name: "Continue with Google" });
  await expect(google).toBeVisible();
  await expect(page.getByText("Only @thapar.edu or @example.com Google accounts.")).toBeVisible();
  const box = await google.boundingBox();
  expect(box?.height ?? 0).toBeGreaterThanOrEqual(38);
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(results.violations.map((v) => v.id)).toEqual([]);
});

test("a thapar.edu Google account signs in and lands signed in", async ({ page }) => {
  const email = `e2e-google-${Date.now()}@thapar.edu`;
  await startGoogle(page, email);
  await expect(page).toHaveURL(/\/home$/);
  await expect(page.getByText(`You're signed in as ${email}`)).toBeVisible();

  const cookies = await page.context().cookies();
  expect(cookies.find((c) => c.name === "session")?.httpOnly).toBe(true);
  expect(cookies.find((c) => c.name === "google_oauth_state")).toBeUndefined();
});

test("a look-alike domain is refused with a clear message", async ({ page }) => {
  await startGoogle(page, `e2e-${Date.now()}@evilthapar.edu`);
  await expect(page).toHaveURL(/\/login\?error=email_not_allowed$/);
  await expect(
    page.getByRole("alert").filter({ hasText: "can't be used to sign in here" }),
  ).toBeVisible();
});

test("cancelling at Google comes back to the sign-in page", async ({ page }) => {
  await page.goto("/login");
  await page.getByRole("checkbox", { name: /18 or older/ }).check();
  await page.getByRole("checkbox", { name: /accept the/ }).check();
  await page.getByRole("button", { name: "Continue with Google" }).click();
  await page.getByRole("link", { name: "Cancel" }).click();
  await expect(page).toHaveURL(/\/login\?error=google_cancelled$/);
  await expect(page.getByRole("alert").filter({ hasText: "cancelled" })).toBeVisible();
});
