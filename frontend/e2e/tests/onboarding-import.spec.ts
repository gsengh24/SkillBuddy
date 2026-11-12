import AxeBuilder from "@axe-core/playwright";
import { existsSync, mkdirSync } from "node:fs";
import path from "node:path";

import { expect, test, type Locator, type Page } from "@playwright/test";

import { settleAnimations } from "./helpers";

/**
 * Onboarding P5 (ADR 0022 screens 6 and 7, ADR 0023) on the synthetic screens page, so no
 * sign-up is used: a synthetic resume PDF read by the real PDF.js in the browser, and pasted
 * text. Checks that nothing from the file or the text is sent anywhere, that no CSP rule is
 * broken, and shoots every state at 390 and 1280px beside its mockup.
 */
const OUT = "screenshots";
const MOCKUPS = "/design/onboarding";
const RESUME = path.join(__dirname, "..", "fixtures", "synthetic-resume.pdf");
const PASTED =
  "Second-year CSE student. I build mobile and web apps with Flutter and React, and I design " +
  "most of my own screens in Figma. Weekend hackathon regular, mostly ML tracks. Off-screen: " +
  "chess and street photography.";
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

async function shoot(target: Page | Locator, name: string) {
  mkdirSync(OUT, { recursive: true });
  await target.screenshot({ path: `${OUT}/${name}.png`, caret: "initial" });
}

async function mockup(page: Page, file: string, name: string) {
  if (existsSync(`${MOCKUPS}/${file}.html`)) {
    await page.goto(`file://${MOCKUPS}/${file}.html`);
    await page.screenshot({ path: `${OUT}/${name}.png`, fullPage: true });
  }
}

/** Every request body and URL the page sends, and any CSP report in the console. */
function watch(page: Page) {
  const sent: string[] = [];
  const csp: string[] = [];
  page.on("request", (request) => sent.push(`${request.url()} ${request.postData() ?? ""}`));
  page.on("console", (message) => {
    if (/Content Security Policy/i.test(message.text())) csp.push(message.text());
  });
  return { sent, csp };
}

function section(page: Page, title: string): Locator {
  return page.locator("section", { has: page.getByRole("heading", { name: title, level: 2 }) });
}

test("resume import reads a PDF in the browser (screen 6)", async ({ page }) => {
  test.setTimeout(120_000);
  await page.emulateMedia({ reducedMotion: "reduce" });
  const { sent, csp } = watch(page);
  // While `held` is set, the scripts PDF.js loads on demand wait, so the reading state stays
  // up for its picture. The route stays for the whole test; anything else passes straight on.
  let held: Promise<void> | null = null;
  await page.route("**/_next/static/**", async (route) => {
    if (held) await held;
    await route.fallback().catch(() => {
      // Already answered (the page moved on): nothing to do.
    });
  });

  for (const { name, width, height } of WIDTHS) {
    await page.setViewportSize({ width, height });
    await page.goto("/design/screens");
    const resume = section(page, "Resume import");
    await resume.scrollIntoViewIfNeeded();
    await expect(
      resume.getByText("Up to 2 MB. Read in your browser, never uploaded or stored."),
    ).toBeVisible();
    await shoot(resume, `onboarding-resume-pick-${name}`);

    let release: () => void = () => {};
    held = new Promise<void>((resolve) => {
      release = resolve;
    });
    // A file picked before the page has hydrated is ignored: pick again until it reads.
    const reading = resume.getByRole("heading", { name: /Reading your resume/ });
    await expect(async () => {
      if (!(await reading.isVisible())) {
        await resume.getByLabel("Choose a resume PDF").setInputFiles(RESUME);
      }
      await expect(reading).toBeVisible({ timeout: 2_000 });
    }).toPass({ timeout: 30_000 });
    await expect(resume.getByText("synthetic-resume.pdf")).toBeVisible();
    await shoot(resume, `onboarding-resume-reading-${name}`);
    held = null;
    release();

    await expect(resume.getByRole("heading", { name: /We found these/ })).toBeVisible({
      timeout: 60_000,
    });
    const skills = resume.getByRole("group", { name: "Skills you offer" });
    for (const skill of ["Flutter", "React", "Figma", "UI design", "Firebase", "Public speaking"]) {
      await expect(skills.getByRole("button", { name: skill, exact: true })).toHaveAttribute(
        "aria-pressed",
        "true",
      );
    }
    const interests = resume.getByRole("group", { name: "Interests" });
    await expect(interests.getByRole("button", { name: "Chess" })).toBeVisible();
    // The made-up person's details never become chips.
    await expect(resume.getByText(/Aarav|example\.com|90000|Patiala/)).toHaveCount(0);
    await resume.getByRole("button", { name: "Figma" }).click();
    await expect(resume.getByRole("button", { name: "Figma" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    await shoot(resume, `onboarding-resume-found-${name}`);
    if (name === "390") await expectNoViolations(page);
    await mockup(page, "06-resume-import", `onboarding-resume-mockup-${name}`);
  }

  // Nothing from the file left the browser.
  expect(sent.filter((line) => /Flutter|Aarav|90000|Patiala/.test(line))).toEqual([]);
  expect(csp).toEqual([]);
});

test("paste anything finds skills without sending the text (screen 7)", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  const { sent, csp } = watch(page);

  for (const { name, width, height } of WIDTHS) {
    await page.setViewportSize({ width, height });
    await page.goto("/design/screens");
    const paste = section(page, "Paste anything");
    await paste.scrollIntoViewIfNeeded();
    const box = paste.getByLabel("Text about you");
    await expect(paste.getByRole("button", { name: "Find my skills" })).toBeDisabled();
    await shoot(paste, `onboarding-paste-empty-${name}`);
    // Typing before the page has hydrated is lost: fill again until the button wakes up.
    await expect(async () => {
      await box.fill(PASTED);
      await expect(paste.getByRole("button", { name: "Find my skills" })).toBeEnabled({
        timeout: 2_000,
      });
    }).toPass({ timeout: 30_000 });
    await shoot(paste, `onboarding-paste-filled-${name}`);
    await paste.getByRole("button", { name: "Find my skills" }).click();
    await expect(paste.getByRole("heading", { name: /We found these/ })).toBeVisible();
    await expect(paste.getByRole("status")).toHaveText("7 kept");
    await shoot(paste, `onboarding-paste-found-${name}`);
    if (name === "390") await expectNoViolations(page);
    // By keyboard: on desktop the button lifts under a hovering pointer and never settles.
    await paste.getByRole("button", { name: /Use these/ }).focus();
    await page.keyboard.press("Enter");
    await expect(paste.getByText("Would add 7 to step 2.")).toBeVisible();
    await mockup(page, "07-paste-anything", `onboarding-paste-mockup-${name}`);
  }

  expect(sent.filter((line) => /Flutter|hackathon/i.test(line))).toEqual([]);
  expect(csp).toEqual([]);
});
