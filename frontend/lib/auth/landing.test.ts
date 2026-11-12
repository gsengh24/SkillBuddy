import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));
const getOnboarding = vi.hoisted(() => vi.fn());
vi.mock("@/lib/onboarding/server", () => ({ getOnboarding }));

import { signedInLanding } from "./landing";
import { safeNextPath } from "./redirect";

const STEPS = ["intents", "offers", "wants", "about"] as const;

beforeEach(() => {
  getOnboarding.mockReset();
});

describe("signedInLanding", () => {
  it("opens step 1 for a new account, from the API's progress", async () => {
    getOnboarding.mockResolvedValue({
      completed_at: null,
      steps: STEPS.map((step) => ({ step, state: "todo" })),
    });
    await expect(signedInLanding()).resolves.toBe("/onboarding");
  });

  it("goes Home when the onboarding call fails, never an error or a loop", async () => {
    getOnboarding.mockImplementation(async () => {
      throw new Error("503");
    });
    await expect(signedInLanding()).resolves.toBe("/home");
  });
});

describe("a deep link wins over the default landing", () => {
  it("keeps a same-site next path and uses /start only without one", () => {
    expect(safeNextPath("/teams/join/abc123")).toBe("/teams/join/abc123");
    expect(safeNextPath(undefined)).toBe("/start");
    expect(safeNextPath("https://evil.example")).toBe("/start");
  });
});
