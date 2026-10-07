import { existsSync, mkdirSync } from "node:fs";

import { expect, test, type Page } from "@playwright/test";

import { signUp } from "./helpers";

/**
 * Screenshots of Home beside the design reference, at the spec's two review widths (390 and
 * 1280px), for the pull request. CI uploads the folder as the "ui-screenshots" artifact. The
 * reference pages are mounted read-only at /design by the Smoke job; without them only the
 * app is captured.
 */
const OUT = "screenshots";
const REFERENCE = "/design/reference-home.html";
const WIDTHS = [
  { name: "390", width: 390, height: 844 },
  { name: "1280", width: 1280, height: 900 },
];

async function shoot(page: Page, name: string) {
  mkdirSync(OUT, { recursive: true });
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
}

test("Home and its reference, at 390 and 1280px", async ({ page, request }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1280, height: 900 });
  await signUp(page, request, "/onboarding");
  await page.getByLabel("Your name", { exact: true }).fill("Dev");
  await page
    .getByLabel("About you", { exact: true })
    .fill("I build React apps and write Python. Looking for a designer for a budgeting app.");
  await page.getByRole("checkbox", { name: /read by AI to find and explain/ }).check();
  await page.getByRole("button", { name: "Save and continue" }).click();
  await expect(page).toHaveURL(/\/profile/);

  await page.goto("/home");
  await page
    .getByLabel("Describe it in your own words")
    .fill("A design partner for a small budgeting app, on weekends.");
  await page.getByRole("button", { name: "Find matches" }).click();
  await expect(page).toHaveURL(/\/home\?item=request-/);
  const opened = page.url();

  for (const { name, width, height } of WIDTHS) {
    await page.setViewportSize({ width, height });
    await page.goto("/home");
    await expect(page.getByRole("heading", { name: "Home", level: 1 })).toBeVisible();
    await shoot(page, `home-${name}`);
    await page.goto(opened);
    await expect(
      page.getByText("“A design partner for a small budgeting app, on weekends.”"),
    ).toBeVisible();
    await shoot(page, `home-request-open-${name}`);
    if (existsSync(REFERENCE)) {
      await page.goto(`file://${REFERENCE}`);
      await shoot(page, `reference-home-${name}`);
    }
  }
});

test("match, intro and chat screens, at 390 and 1280px", async ({ page }) => {
  for (const { name, width, height } of WIDTHS) {
    await page.setViewportSize({ width, height });
    await page.goto("/design/screens");
    await expect(page.getByRole("heading", { name: "Screens", level: 1 })).toBeVisible();
    await shoot(page, `screens-${name}`);
  }
});
