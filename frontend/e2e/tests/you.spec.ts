import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { settleAnimations, signUp } from "./helpers";

async function expectNoViolations(page: Page) {
  await settleAnimations(page);
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
 * The You page (design spec section 13): it loads, a change shows the Save bar, Save sends
 * one request and keeps the value, Discard puts it back, and the preview shows the edit.
 */
test("edit the profile on You, save, discard and preview", async ({ page, request }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 390, height: 844 });
  await signUp(page, request, "/onboarding");
  await page.getByLabel("Your name", { exact: true }).fill("Meera");
  await page
    .getByLabel("About you", { exact: true })
    .fill("I design mobile apps and want a developer to pair with on weekends.");
  await page.getByRole("checkbox", { name: /read by AI to find and explain/ }).check();
  await page.getByRole("button", { name: "Save and continue" }).click();
  await expect(page).toHaveURL(/\/you\?welcome=1$/);

  await page.goto("/you");
  await expect(page.getByRole("heading", { level: 1, name: /Your profile\./ })).toBeVisible();
  await expect(page.getByRole("region", { name: "Unsaved changes" })).toHaveCount(0);
  await expectNoViolations(page);

  // A change shows the Save bar; saving sends one PATCH and the value stays after a reload.
  await page.getByLabel("City", { exact: true }).fill("Bengaluru");
  const bar = page.getByRole("region", { name: "Unsaved changes" });
  await expect(bar).toBeVisible();
  await expectNoViolations(page);
  const saves: string[] = [];
  page.on("request", (req) => {
    if (req.url().includes("/api/v1/me/profile") && req.method() !== "GET") {
      saves.push(req.method());
    }
  });
  await bar.getByRole("button", { name: "Save changes" }).click();
  await expect(bar).toHaveCount(0);
  expect(saves).toEqual(["PATCH"]);
  await page.reload();
  await expect(page.getByLabel("City", { exact: true })).toHaveValue("Bengaluru");

  // Discard puts the saved value back.
  await page.getByLabel("City", { exact: true }).fill("Chennai");
  await page.getByRole("button", { name: "Discard" }).click();
  await expect(page.getByLabel("City", { exact: true })).toHaveValue("Bengaluru");

  // The preview shows the edit before it is saved, and Escape closes it.
  await page.getByLabel("City", { exact: true }).fill("Chennai");
  await page.getByRole("button", { name: "See how others see you" }).click();
  const preview = page.getByRole("dialog", { name: "How others see you" });
  await expect(preview).toContainText("Chennai");
  await expectNoViolations(page);
  await page.keyboard.press("Escape");
  await expect(preview).toHaveCount(0);
  await expect(page.getByRole("button", { name: "See how others see you" })).toBeFocused();
  await page.getByRole("button", { name: "Discard" }).click();

  // At desktop width: the numbered section list, and no violations there either.
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.getByRole("link", { name: /Danger zone/ }).click();
  await expect(page).toHaveURL(/#s-danger$/);
  await expectNoViolations(page);

  // The delete dialog needs the box and DELETE, and Escape leaves the account alone.
  await page.getByRole("button", { name: "Delete my account…" }).click();
  const confirm = page.getByRole("dialog", { name: "Delete account" });
  await expect(confirm.getByRole("button", { name: "Delete my account" })).toBeDisabled();
  await expectNoViolations(page);
  await page.keyboard.press("Escape");
  await expect(confirm).toHaveCount(0);
});
