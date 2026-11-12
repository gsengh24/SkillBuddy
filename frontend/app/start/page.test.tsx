import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));
const REDIRECT = vi.hoisted(() => new Error("NEXT_REDIRECT"));
const redirect = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({
  redirect: (to: string) => {
    redirect(to);
    throw REDIRECT;
  },
}));
const getCurrentUser = vi.hoisted(() => vi.fn());
vi.mock("@/lib/auth/session", () => ({ getCurrentUser }));
const signedInLanding = vi.hoisted(() => vi.fn());
vi.mock("@/lib/auth/landing", () => ({ signedInLanding }));

import StartPage from "./page";

beforeEach(() => {
  redirect.mockReset();
  getCurrentUser.mockReset();
  signedInLanding.mockReset();
});

describe("/start", () => {
  it("redirects a signed-in person to where the API's progress says", async () => {
    getCurrentUser.mockResolvedValue({ id: "u1" });
    signedInLanding.mockResolvedValue("/onboarding");
    await expect(StartPage()).rejects.toBe(REDIRECT);
    expect(redirect).toHaveBeenCalledWith("/onboarding");
  });

  it("sends a signed-out visitor to sign in", async () => {
    getCurrentUser.mockResolvedValue(null);
    await expect(StartPage()).rejects.toBe(REDIRECT);
    expect(redirect).toHaveBeenCalledWith("/login");
    expect(signedInLanding).not.toHaveBeenCalled();
  });
});
