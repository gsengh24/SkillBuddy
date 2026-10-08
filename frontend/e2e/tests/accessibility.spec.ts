import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { settleAnimations } from "./helpers";

/**
 * Automated accessibility check (axe-core, WCAG 2.0/2.1 A and AA rules, including colour
 * contrast) on the style guide and the sign-in page, at desktop and phone sizes. The
 * style guide only exists in development, which is what the CI stack runs.
 */
const VIEWPORTS = [
  { name: "desktop", width: 1280, height: 900 },
  { name: "phone", width: 390, height: 844 },
];

async function expectNoViolations(page: Page) {
  await settleAnimations(page);
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  const summary = results.violations.map(
    (violation) =>
      `${violation.id} (${violation.impact}): ${violation.help}\n  ${violation.nodes
        .slice(0, 5)
        .map((node) => node.target.join(" "))
        .join("\n  ")}`,
  );
  expect(summary, summary.join("\n")).toEqual([]);
}

for (const viewport of VIEWPORTS) {
  test.describe(`at ${viewport.name} size`, () => {
    test.use({ viewport: { width: viewport.width, height: viewport.height } });

    test("the style guide has no accessibility violations", async ({ page }) => {
      await page.goto("/design");
      await expect(page.getByRole("heading", { level: 1, name: "Design system" })).toBeVisible();
      await expectNoViolations(page);
    });

    test("the sign-in page has no accessibility violations", async ({ page }) => {
      await page.goto("/login");
      await expect(page.getByRole("heading", { name: /Sign in to/ })).toBeVisible();
      await expectNoViolations(page);

      // The error state too: submitting without the tick boxes shows an alert.
      await page.getByLabel("Email address").fill("someone@example.com");
      await page.getByRole("button", { name: "Email me a code" }).click();
      // (Next.js also renders an empty role="alert" route announcer, so match the text.)
      await expect(page.getByRole("alert").filter({ hasText: /18 or older/ })).toBeVisible();
      await expectNoViolations(page);
    });
  });
}

test("sign-in controls are at least 44px tall on a phone", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/login");
  for (const control of [
    page.getByRole("button", { name: "Email me a code" }),
    page.getByLabel("Email address"),
  ]) {
    const box = await control.boundingBox();
    expect(box?.height ?? 0).toBeGreaterThanOrEqual(44);
  }
});
