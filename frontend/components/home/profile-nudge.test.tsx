import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { NUDGE_DISMISSED_KEY, type NudgeStrength } from "@/lib/profile/nudge";

import { ProfileNudge, resetProfileNudgeForTests } from "./profile-nudge";

const USER = { created_at: "2026-10-01T10:00:00Z", session_started_at: "2026-10-03T09:00:00Z" };
const STRENGTH: NudgeStrength = {
  done: 4,
  total: 7,
  missing: [
    { label: "Add 3 skills you offer", href: "#s-skills" },
    { label: "Add a link", href: "#s-links" },
    { label: "Share your goal", href: "#s-looking" },
  ],
};

function reduceMotion(reduce: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: reduce && query.includes("reduce"),
    media: query,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  }));
}

async function shown(strength: NudgeStrength | null = STRENGTH, user = USER) {
  const view = render(<ProfileNudge user={user} strength={strength} />);
  await act(async () => {
    await vi.advanceTimersByTimeAsync(1500);
  });
  return view;
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  window.localStorage.clear();
  resetProfileNudgeForTests();
  reduceMotion(false);
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("ProfileNudge", () => {
  it("waits, then shows the count and at most two missing links", async () => {
    render(<ProfileNudge user={USER} strength={STRENGTH} />);
    expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500);
    });
    expect(screen.getByRole("complementary", { name: "Finish your profile" })).toBeInTheDocument();
    expect(screen.getByText("4 of 7 done. Fuller profiles get better matches.")).toBeVisible();
    expect(screen.getByText("4/7")).toBeInTheDocument();
    const links = screen.getAllByRole("link").map((a) => [a.textContent, a.getAttribute("href")]);
    expect(links).toEqual([
      ["Add 3 skills you offer", "/you#s-skills"],
      ["Add a link", "/you#s-links"],
      ["Finish profile →", "/you#s-skills"],
    ]);
  });

  it("shows nothing in the first session or without a profile", async () => {
    await shown(STRENGTH, { ...USER, session_started_at: "2026-10-01T10:00:20Z" });
    expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
    await shown(null);
    expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
  });

  it("closing hides it and remembers this session", async () => {
    await shown();
    await userEvent.click(screen.getByRole("button", { name: "Dismiss until next sign-in" }));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(400);
    });
    expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
    expect(window.localStorage.getItem(NUDGE_DISMISSED_KEY)).toBe(USER.session_started_at);
  });

  it("stays hidden when this session was closed before", async () => {
    window.localStorage.setItem(NUDGE_DISMISSED_KEY, USER.session_started_at);
    await shown();
    expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
  });

  it("Escape closes it when focus is inside", async () => {
    await shown();
    screen.getByRole("link", { name: "Add a link" }).focus();
    await userEvent.keyboard("{Escape}");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(400);
    });
    expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
    expect(window.localStorage.getItem(NUDGE_DISMISSED_KEY)).toBe(USER.session_started_at);
  });

  it("following a link does not count as closing it", async () => {
    await shown();
    expect(window.localStorage.getItem(NUDGE_DISMISSED_KEY)).toBeNull();
  });

  it("adds no transform classes with reduced motion", async () => {
    reduceMotion(true);
    await shown();
    const card = screen.getByRole("complementary");
    expect(card.className).not.toMatch(/translate|scale|transition|origin-/);
  });
});
