import AxeBuilder from "@axe-core/playwright";
import { existsSync, mkdirSync } from "node:fs";

import { expect, test, type Page } from "@playwright/test";

import { settleAnimations } from "./helpers";

/**
 * Onboarding P4 (ADR 0022) on the synthetic screens page, so no sign-up is used (codes are
 * rate limited per IP): the soft gate (screen 9) opened by the real Send intro button when
 * the API answers `skills_required`, and the Home nudges (screen 11). Home with an unfinished
 * profile (screen 8) and You (screen 10) are shot in onboarding.spec with its account.
 */
const OUT = "screenshots";
const MOCKUPS = "/design/onboarding";
const WIDTHS = [
  { name: "390", width: 390, height: 844 },
  { name: "1280", width: 1280, height: 900 },
];

const PROGRESS = {
  completed_at: null,
  next_step: "review",
  steps: [
    { step: "intents", state: "saved" },
    { step: "offers", state: "saved" },
    { step: "wants", state: "saved" },
    { step: "about", state: "saved" },
  ],
  intents: ["build_together"],
  offer_skills: ["React"],
  want_skills: [],
  interest_tags: [],
  want_note: "",
  study_year: null,
  branch: null,
  available_days: [],
  weekly_hours: null,
  display_name: "",
  strength: { percent: 43, done: 3, total: 7, missing: ["offers"] },
};

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

async function shoot(page: Page, name: string) {
  mkdirSync(OUT, { recursive: true });
  await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true, caret: "initial" });
}

async function mockup(page: Page, file: string, name: string) {
  if (existsSync(`${MOCKUPS}/${file}.html`)) {
    await page.goto(`file://${MOCKUPS}/${file}.html`);
    await shoot(page, name);
  }
}

async function openGate(page: Page) {
  await page.goto("/design/screens");
  await expect(page.getByRole("heading", { name: "Screens", level: 1 })).toBeVisible();
  const dialog = page.getByRole("dialog", { name: "Add 3 skills first" });
  // The first match card: open the note, then send it. A click that lands before the page
  // has hydrated does nothing, so each step is retried until its result shows.
  const note = page.getByRole("textbox", { name: "A short hello (optional)" }).first();
  await expect(async () => {
    if (!(await note.isVisible())) {
      await page.getByRole("button", { name: "Send intro" }).first().click();
    }
    await expect(note).toBeVisible({ timeout: 2_000 });
  }).toPass({ timeout: 30_000 });
  await expect(async () => {
    if (!(await dialog.isVisible())) {
      await page.getByRole("button", { name: "Send intro" }).first().click();
    }
    await expect(dialog).toBeVisible({ timeout: 2_000 });
  }).toPass({ timeout: 30_000 });
  return dialog;
}

test("the soft gate before an intro (screen 9)", async ({ page }) => {
  await page.route("**/api/v1/matches/*/intro", (route) =>
    route.fulfill({
      status: 409,
      json: {
        error: {
          code: "skills_required",
          message: "Add 3 skills you offer first.",
          request_id: "e2e",
          details: null,
        },
      },
    }),
  );
  await page.route("**/api/v1/me/onboarding", (route) => route.fulfill({ json: PROGRESS }));
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: "reduce" });

  const dialog = await openGate(page);
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("status")).toHaveText("1 / 3");
  await expect(dialog.getByRole("button", { name: "Save and continue" })).toBeDisabled();
  await expect(
    dialog.getByRole("group", { name: "Skills you offer" }).getByRole("button", { name: "React" }),
  ).toHaveAttribute("aria-pressed", "true");
  await expectNoViolations(page);

  // Focus stays inside while it is open; Escape closes it and the intro is not sent.
  for (let i = 0; i < 15; i++) await page.keyboard.press("Tab");
  expect(await dialog.evaluate((node) => node.contains(document.activeElement))).toBe(true);
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(page.getByRole("button", { name: "Send intro" }).first()).toBeFocused();

  for (const { name, width, height } of WIDTHS) {
    await page.setViewportSize({ width, height });
    const shown = await openGate(page);
    await shown.getByRole("button", { name: "Figma" }).click();
    await expect(shown.getByRole("status")).toHaveText("2 / 3");
    await shoot(page, `onboarding-soft-gate-${name}`);
    await page.keyboard.press("Escape");
    await mockup(page, "09-soft-gate", `onboarding-soft-gate-mockup-${name}`);
  }
});

test("the Home nudges (screen 11)", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const { name, width, height } of WIDTHS) {
    await page.setViewportSize({ width, height });
    await page.goto("/design/screens");
    const nudges = page.getByRole("region", { name: "Suggestion" });
    await expect(nudges).toHaveCount(2);
    await expect(nudges.first()).toContainText("You joined ML study circle.");
    await expect(nudges.last()).toContainText("Add your availability");
    mkdirSync(OUT, { recursive: true });
    await page
      .locator("section", { has: page.getByRole("heading", { name: "Home nudges" }) })
      .screenshot({ path: `${OUT}/onboarding-nudges-${name}.png` });
    await mockup(page, "11-in-context-nudge", `onboarding-nudges-mockup-${name}`);
  }
});
