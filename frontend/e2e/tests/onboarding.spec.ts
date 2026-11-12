import AxeBuilder from "@axe-core/playwright";
import { existsSync, mkdirSync } from "node:fs";

import { expect, test, type Page } from "@playwright/test";

import { settleAnimations, signUp } from "./helpers";

/**
 * Onboarding steps 1–5 (ADR 0022) end to end: pick, skip, leave and resume, finish, check
 * the card and confirm it. One sign-up (sign-up codes are rate limited per IP), then screenshots of
 * every step at 390 and 1280px beside its mockup, for the pull request.
 */
const OUT = "screenshots";
const MOCKUPS = "/design/onboarding";
const STEPS = [
  { step: "intents", heading: /What brings you here/, mockup: "01-what-brings-you-here" },
  { step: "offers", heading: /What are you good at/, mockup: "02-what-you-offer" },
  { step: "wants", heading: /What are you looking for/, mockup: "03-what-you-want" },
  { step: "about", heading: /Almost done/, mockup: "04-a-bit-about-you" },
] as const;
const WIDTHS = [
  { name: "390", width: 390, height: 844 },
  { name: "1280", width: 1280, height: 900 },
];

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

test("onboarding steps: pick, skip, resume, finish, check the card", async ({ page, request }) => {
  test.setTimeout(180_000);
  await page.setViewportSize({ width: 390, height: 844 });
  await signUp(page, request, "/onboarding");

  // Step 1: no skip, and Continue waits for a pick.
  await expect(page.getByRole("heading", { level: 1, name: /What brings you here/ })).toBeVisible();
  await expect(page.getByText("Step 1 of 4")).toBeVisible();
  await expect(page.getByRole("button", { name: "Skip for now" })).toHaveCount(0);
  const next = page.getByRole("button", { name: /Continue/ });
  await expect(next).toBeDisabled();
  await page.getByRole("button", { name: /Build together/ }).click();
  await page.getByRole("button", { name: /Skill exchange/ }).click();
  await expect(page.getByRole("status").filter({ hasText: "2 selected" })).toBeVisible();
  await expectNoViolations(page);
  await next.click();

  // Step 2: chips are toggle buttons.
  await expect(page.getByRole("heading", { level: 1, name: /What are you good at/ })).toBeVisible();
  const coding = page.getByRole("group", { name: "Coding" });
  await coding.getByRole("button", { name: "React" }).click();
  await page.getByRole("group", { name: "Design" }).getByRole("button", { name: "Figma" }).click();
  await expect(coding.getByRole("button", { name: "React" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expectNoViolations(page);
  await page.getByRole("button", { name: /Continue/ }).click();

  // Step 3: skip it.
  await expect(
    page.getByRole("heading", { level: 1, name: /What are you looking for/ }),
  ).toBeVisible();
  await expect(page.getByRole("region", { name: "Pairs well with what you offer" })).toBeVisible();
  await expectNoViolations(page);
  await page.getByRole("button", { name: "Skip for now" }).click();
  await expect(page.getByRole("heading", { level: 1, name: /Almost done/ })).toBeVisible();

  // Leave and come back: onboarding resumes at step 4.
  await page.goto("/home");
  await page.goto("/onboarding");
  await expect(page.getByRole("heading", { level: 1, name: /Almost done/ })).toBeVisible();
  await expect(page.getByText("Step 4 of 4")).toBeVisible();
  // Home doesn't treat an unfinished profile as finished.
  await page.goto("/home");
  await expect(page.getByRole("link", { name: "Create your profile" })).toBeVisible();
  await page.goto("/onboarding");

  // Step 4: a radiogroup for the year; the consent line (unchanged) is required to finish.
  await page.getByRole("radio", { name: "2nd" }).click();
  await expect(page.getByRole("radio", { name: "2nd" })).toHaveAttribute("aria-checked", "true");
  await page.getByRole("button", { name: "Saturday" }).click();
  await page.getByRole("button", { name: /Finish/ }).click();
  await expect(page.getByRole("alert").filter({ hasText: /agree to how AI/ })).toBeVisible();
  await page.getByRole("checkbox", { name: /read by AI to find and explain/ }).check();
  await expectNoViolations(page);
  await page.getByRole("button", { name: /Finish/ }).click();

  // Step 5: the card others will see. No AI keys in CI, so the template version shows.
  await expect(page).toHaveURL(/\/onboarding\/review$/);
  const card = page.getByRole("article", { name: "Preview of your match card" });
  await expect(card).toBeVisible({ timeout: 30_000 });
  await expect(card.getByText("We'll polish this shortly.")).toBeVisible();
  await expect(card.getByText("React", { exact: true })).toBeVisible();
  await expect(page.getByLabel("About you")).toHaveValue(/React/);
  await expectNoViolations(page);

  // Earlier picks are kept when going back to a step.
  await page.getByRole("button", { name: "Edit" }).click();
  await expect(
    page.getByRole("group", { name: "Coding" }).getByRole("button", { name: "React" }),
  ).toHaveAttribute("aria-pressed", "true");

  // Screenshots of every step beside its mockup, and of step 5's three states. The loading
  // and ready states are shown by answering the page's polls with a pending or AI-written
  // version of this profile (CI has no AI keys).
  const real = (await (await page.request.get("/api/v1/me/profile")).json()) as Record<
    string,
    unknown
  >;
  const STATES = {
    loading: { ...real, parse_status: "pending", understanding: null },
    ready: {
      ...real,
      parse_status: "parsed",
      parse_source: "llm",
      about_text:
        "I build React front ends and design in Figma. Looking to swap skills on weekends.",
      understanding: {
        title: "Frontend builder looking to swap skills",
        summary: "Builds React front ends and designs in Figma; free on weekends to swap skills.",
        offers: ["React", "Figma"],
        seeks: [],
        interests: [],
        availability: "Sat",
      },
    },
    fallback: null,
  } as const;
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const { name, width, height } of WIDTHS) {
    await page.setViewportSize({ width, height });
    for (const { step, heading, mockup } of STEPS) {
      await page.goto(`/onboarding?step=${step}`);
      await expect(page.getByRole("heading", { level: 1, name: heading })).toBeVisible();
      await shoot(page, `onboarding-${step}-${name}`);
      if (existsSync(`${MOCKUPS}/${mockup}.html`)) {
        await page.goto(`file://${MOCKUPS}/${mockup}.html`);
        await shoot(page, `onboarding-${step}-mockup-${name}`);
      }
    }
    for (const [state, body] of Object.entries(STATES)) {
      await page.unrouteAll();
      if (body) {
        await page.route("**/api/v1/me/profile", (route) => route.fulfill({ json: body }));
      }
      await page.goto("/onboarding/review");
      await expect(
        page.getByRole("article", {
          name: state === "loading" ? "Your match card is loading" : "Preview of your match card",
        }),
      ).toBeVisible({ timeout: 30_000 });
      await shoot(page, `onboarding-review-${state}-${name}`);
    }
    await page.unrouteAll();
    if (existsSync(`${MOCKUPS}/05-check-what-we-understood.html`)) {
      await page.goto(`file://${MOCKUPS}/05-check-what-we-understood.html`);
      await shoot(page, `onboarding-review-mockup-${name}`);
    }
  }

  // "Looks good" finishes onboarding and goes Home; onboarding is then closed.
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/onboarding/review");
  await expect(page.getByRole("article", { name: "Preview of your match card" })).toBeVisible({
    timeout: 30_000,
  });
  await page.getByRole("button", { name: /Looks good/ }).click();
  await expect(page).toHaveURL(/\/home/);
  await page.goto("/onboarding");
  await expect(page).toHaveURL(/\/you$/);
});
