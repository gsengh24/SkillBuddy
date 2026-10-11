import { describe, expect, it } from "vitest";

import { shouldShowProfileNudge, type NudgeStrength } from "./nudge";

const CREATED = "2026-10-01T10:00:00Z";
const FIRST = "2026-10-01T10:00:30Z";
const LATER = "2026-10-03T09:00:00Z";
const INCOMPLETE: NudgeStrength = {
  done: 5,
  total: 7,
  missing: [{ label: "Add a link", href: "#s-links" }],
};
const COMPLETE: NudgeStrength = { done: 7, total: 7, missing: [] };

function show(over: {
  session?: string;
  strength?: NudgeStrength | null;
  dismissedFor?: string | null;
}) {
  return shouldShowProfileNudge({
    user: { created_at: CREATED, session_started_at: over.session ?? LATER },
    strength: over.strength === undefined ? INCOMPLETE : over.strength,
    dismissedFor: over.dismissedFor ?? null,
  });
}

describe("shouldShowProfileNudge", () => {
  it("is false in the session that made the account", () => {
    expect(show({ session: FIRST })).toBe(false);
  });
  it("is true for a returning session with an incomplete profile", () => {
    expect(show({})).toBe(true);
  });
  it("is false for a complete profile", () => {
    expect(show({ strength: COMPLETE })).toBe(false);
  });
  it("is false with no profile", () => {
    expect(show({ strength: null })).toBe(false);
  });
  it("is false when dismissed in this session", () => {
    expect(show({ dismissedFor: LATER })).toBe(false);
  });
  it("is true when dismissed in a previous session", () => {
    expect(show({ dismissedFor: "2026-10-02T08:00:00Z" })).toBe(true);
  });
  it("is false when the API sent no session start", () => {
    expect(
      shouldShowProfileNudge({
        user: { created_at: CREATED },
        strength: INCOMPLETE,
        dismissedFor: null,
      }),
    ).toBe(false);
  });
});
