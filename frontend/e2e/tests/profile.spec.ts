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
 * Onboarding end to end: the stack runs with no AI keys, so the description is read by the
 * template fallback in the worker. Checked at phone size, where most students will use it.
 */
test("create a profile, see what was understood, correct it, pause matching", async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await signUp(page, request, "/onboarding");
  await expect(page.getByRole("heading", { name: "Tell us about you" })).toBeVisible();
  await expectNoViolations(page);

  await page.getByLabel("Your name", { exact: true }).fill("Asha");
  await page
    .getByLabel("About you", { exact: true })
    .fill(
      "I can build React apps and write Python. Looking for a designer, a backend dev. " +
        "I love hiking and chess. Free 4-6 hours a week, mostly weekends.",
    );
  await page.getByRole("checkbox", { name: "Hindi" }).check();

  // The consent line is required on the first save.
  await page.getByRole("button", { name: "Save and continue" }).click();
  await expect(page.getByRole("alert").filter({ hasText: /agree to how AI/ })).toBeVisible();
  await page.getByRole("checkbox", { name: /read by AI to find and explain/ }).check();
  await page.getByRole("button", { name: "Save and continue" }).click();

  await expect(page).toHaveURL(/\/profile\?welcome=1$/);
  await expect(page.getByRole("heading", { name: /how we'll describe you/ })).toBeVisible({
    timeout: 60_000,
  });
  await expect(page.getByText("designer", { exact: true })).toBeVisible();
  await expectNoViolations(page);

  await page.getByRole("button", { name: "Correct this" }).click();
  await page.getByLabel("Interests", { exact: true }).fill("chess, trekking");
  await page.getByRole("button", { name: "Save corrections" }).click();
  await expect(page.getByText("Edited by you.")).toBeVisible();
  await expect(page.getByText("trekking", { exact: true })).toBeVisible();

  const toggle = page.getByRole("switch", { name: /Show me in new matches/ });
  await toggle.uncheck();
  await expect(page.getByText(/won't be suggested to anyone new/)).toBeVisible();

  // Onboarding is only for people without a profile.
  await page.goto("/onboarding");
  await expect(page).toHaveURL(/\/profile$/);
  await expect(toggle).not.toBeChecked();
});
