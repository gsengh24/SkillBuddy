import { expect, test } from "@playwright/test";

import { codeFromMailpit } from "./helpers";

test("sign up with an emailed code, reach home, sign out", async ({ page, request }) => {
  const email = `e2e-${Date.now()}@example.com`;

  // Protected pages send signed-out visitors to the login page.
  await page.goto("/home");
  await expect(page).toHaveURL(/\/login\?next=%2Fhome/);

  // Step 1: email plus the age and terms confirmations.
  await page.getByLabel("Email address").fill(email);
  await page.getByRole("checkbox", { name: /18 or older/ }).check();
  await page.getByRole("checkbox", { name: /accept the/ }).check();
  await page.getByRole("button", { name: "Email me a code" }).click();

  // Step 2: the code from the email (delivered by the worker to Mailpit).
  await expect(page.getByRole("heading", { name: "Check your email" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Resend code in \d+s/ })).toBeDisabled();
  const code = await codeFromMailpit(request, email);
  await page.getByLabel("Sign-in code").fill(code);
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page).toHaveURL(/\/home$/);
  await expect(page.getByText(`You're signed in as ${email}`)).toBeVisible();

  // On a phone the app shell shows a bottom tab bar with 44px+ touch targets.
  await page.setViewportSize({ width: 390, height: 844 });
  const tabs = page.getByRole("navigation", { name: "Main" }).getByRole("link");
  await expect(tabs).toHaveText(["Home", "Spaces", "You"]);
  for (const tab of await tabs.all()) {
    const box = await tab.boundingBox();
    expect(box?.height ?? 0).toBeGreaterThanOrEqual(44);
    expect(box?.width ?? 0).toBeGreaterThanOrEqual(44);
  }
  await page.setViewportSize({ width: 1280, height: 720 });

  // The session cookie is httpOnly and SameSite=Lax; the CSRF cookie is readable.
  const cookies = await page.context().cookies();
  const session = cookies.find((cookie) => cookie.name === "session");
  expect(session?.httpOnly).toBe(true);
  expect(session?.sameSite).toBe("Lax");
  expect(cookies.find((cookie) => cookie.name === "csrf_token")?.httpOnly).toBe(false);

  // Sign out from account settings (a CSRF-protected POST).
  await page.getByRole("link", { name: "Account settings" }).click();
  await expect(page.getByRole("heading", { name: "Account and security" })).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page).toHaveURL(/\/login/);

  await page.goto("/home");
  await expect(page).toHaveURL(/\/login/);
});
