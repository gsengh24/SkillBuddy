import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { readFile } from "node:fs/promises";

import { linkFromMailpit, settleAnimations, signUp } from "./helpers";

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
 * Onboarding end to end: the stack runs with no AI keys, so the description is read by the
 * template fallback in the worker. Checked at phone size, where most students will use it.
 */
test("create a profile, see what was understood, correct it, pause matching, edit it on You, use the account controls", async ({
  page,
  request,
}) => {
  test.setTimeout(240_000);
  await page.setViewportSize({ width: 390, height: 844 });
  const email = await signUp(page, request, "/onboarding");
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

  await expect(page).toHaveURL(/\/you\?welcome=1$/);
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
  await expect(page).toHaveURL(/\/you$/);
  await expect(toggle).not.toBeChecked();

  /*
   * The You page (design spec section 13), with the same account (sign-ups are rate
   * limited per IP, so this doesn't make a new one): it loads, a change shows the Save
   * bar, Save sends one request and keeps the value, Discard puts it back, and the preview
   * shows the edit.
   */
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

  // Account controls (Prompt 12C): this device is listed, the data file arrives by email
  // and downloads, and the account pauses and resumes.
  await expect(page.getByRole("list", { name: "Signed-in devices" })).toContainText("This device");
  await page.getByRole("button", { name: "Request" }).click();
  await expect(page.getByRole("status").filter({ hasText: /email you a link/ })).toBeVisible();
  const link = await linkFromMailpit(request, email, "data is ready");
  await page.goto(link);
  await expect(page.getByRole("heading", { name: "Download your data" })).toBeVisible();
  await expectNoViolations(page);
  const downloading = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download the file" }).click();
  const file = JSON.parse(await readFile(await (await downloading).path(), "utf8")) as {
    account: { email: string };
  };
  expect(file.account.email).toBe(email);

  await page.goto("/you#s-danger");
  await page.getByRole("button", { name: "Pause" }).click();
  await expect(page.getByText("Your account is paused")).toBeVisible();
  await expectNoViolations(page);
  await page.getByRole("button", { name: "Resume" }).click();
  await expect(page.getByText("Pause my account")).toBeVisible();
});
