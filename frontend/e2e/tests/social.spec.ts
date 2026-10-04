import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { signUp } from "./helpers";

/**
 * The notifications and messages screens render for a new account (empty states) with no
 * accessibility violations, at phone size. The intro flow itself (send, accept, decline)
 * is covered by the API integration tests and the component tests, since who gets matched
 * in the shared CI stack depends on the other test accounts.
 */
test("notifications and messages pages are accessible on a phone", async ({ page, request }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await signUp(page, request, "/notifications");

  await expect(page.getByRole("heading", { name: "Notifications", level: 1 })).toBeVisible();
  await expect(page.getByText("No intros waiting.")).toBeVisible();
  let results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(results.violations.map((v) => v.id)).toEqual([]);

  await page.goto("/messages");
  await expect(page.getByRole("heading", { name: "Messages", level: 1 })).toBeVisible();
  await expect(page.getByText(/No connections yet/)).toBeVisible();
  results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(results.violations.map((v) => v.id)).toEqual([]);
});

test("a conversation you're not part of is not found", async ({ page, request }) => {
  await signUp(page, request, "/messages");
  // signUp returns once "Sign in" is clicked: wait until the session is set.
  await expect(page.getByRole("heading", { name: "Messages", level: 1 })).toBeVisible();
  await page.goto("/messages/00000000-0000-4000-8000-000000000000");
  await expect(page.getByText("This page could not be found.")).toBeVisible();
  await expect(page.getByRole("textbox")).toHaveCount(0);
});

test("the pair spaces page is accessible on a phone", async ({ page, request }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await signUp(page, request, "/spaces");
  await expect(page.getByRole("heading", { name: "Pair spaces", level: 1 })).toBeVisible();
  await expect(page.getByText(/No connections yet/)).toBeVisible();
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  expect(results.violations.map((v) => v.id)).toEqual([]);
});
