import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { signUp } from "./helpers";

async function expectNoViolations(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  const summary = results.violations.map(
    (v) =>
      `${v.id} (${v.impact}): ${v.help}\n  ${v.nodes.map((n) => n.target.join(" ")).join("\n  ")}`,
  );
  expect(summary, summary.join("\n")).toEqual([]);
}

/**
 * Discover end to end on a phone: create a profile, ask for matches, and see the request
 * finish (the CI stack has no AI keys, so the template path runs in the worker). Whether
 * anyone fits depends on which other e2e accounts exist, so both outcomes are accepted.
 */
test("ask for matches from Discover and see the request finish", async ({ page, request }) => {
  test.setTimeout(150_000);
  await page.setViewportSize({ width: 390, height: 844 });
  await signUp(page, request, "/onboarding");

  await page.getByLabel("Your name", { exact: true }).fill("Dev");
  await page
    .getByLabel("About you", { exact: true })
    .fill("I can build React apps and write Python. Looking for a designer. I love chess.");
  await page.getByRole("checkbox", { name: /read by AI to find and explain/ }).check();
  await page.getByRole("button", { name: "Save and continue" }).click();
  await expect(page).toHaveURL(/\/you/);

  // Navigate directly: in the dev-mode CI stack, Next.js's dev indicator sits over the
  // bottom-left of the screen, on top of the phone tab bar.
  await expect(page.getByRole("link", { name: "Home" })).toHaveAttribute("href", "/home");
  await page.goto("/home");
  await expect(page.getByRole("heading", { name: "Home", level: 1 })).toBeVisible();
  await expectNoViolations(page);

  // Bottom tab bar on a phone, with 44px targets.
  const tabs = page.getByRole("navigation", { name: "Main" }).getByRole("link");
  for (const tab of await tabs.all()) {
    expect((await tab.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(44);
  }

  // On a phone the composer opens (and shows the intent chips) once the text has focus.
  await page
    .getByLabel("Describe it in your own words")
    .fill("A designer to build a small budgeting app with, on weekends.");
  await page.getByRole("button", { name: /Build together/ }).click();
  await page.getByRole("button", { name: "Find matches" }).click();

  await expect(
    page.getByText("“A designer to build a small budgeting app with, on weekends.”"),
  ).toBeVisible();
  await expect(page.getByText(/matches? ready\.|Nobody fits yet/).first()).toBeVisible({
    timeout: 120_000,
  });
  await expectNoViolations(page);

  await page.getByRole("button", { name: "Close this request" }).click();
  await expect(page.getByText("Closed")).toBeVisible();
});
