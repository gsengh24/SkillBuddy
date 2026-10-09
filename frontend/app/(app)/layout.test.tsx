import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/errors";
import { profileSchema, type User } from "@/lib/api/schemas";
import { getCurrentUser } from "@/lib/auth/session";
import { getMyProfile } from "@/lib/profile/server";

import SignedInLayout from "./layout";

vi.mock("@/lib/auth/session", () => ({ getCurrentUser: vi.fn() }));
vi.mock("@/lib/profile/server", () => ({ getMyProfile: vi.fn() }));
vi.mock("@/lib/social/server", () => ({ getUnreadCount: vi.fn(async () => 0) }));

const USER = { id: "11111111-0000-4000-8000-000000000001", email: "a@example.com" } as User;
const child = <p>page</p>;
// Parsed, so the fields this test doesn't set get the API's defaults.
const PROFILE = profileSchema.parse({
  user_id: USER.id,
  display_name: "Asha",
  about_text: "I build things on weekends.",
  links: [],
  timezone: "Asia/Kolkata",
  languages: ["en"],
  visibility: "matchable",
  parse_status: "parsed",
  parse_source: "template",
  understanding: null,
  ai_consent_version: "v1",
  ai_consent_at: null,
  ai_consent_current: true,
  created_at: "2026-10-08T00:00:00Z",
  updated_at: "2026-10-08T00:00:00Z",
});

async function shellProps() {
  const element = (await SignedInLayout({ children: child })) as {
    props: { profileComplete: number | null; children: unknown };
  };
  return element.props;
}

describe("SignedInLayout", () => {
  beforeEach(() => {
    vi.mocked(getCurrentUser).mockResolvedValue(USER);
  });

  it("renders the page alone when signed out, so the page can redirect to /login", async () => {
    vi.mocked(getCurrentUser).mockResolvedValue(null);
    expect(await SignedInLayout({ children: child })).toBe(child);
    expect(getMyProfile).not.toHaveBeenCalled();
  });

  it("shows 'no profile yet' when the API has none (the onboarding path)", async () => {
    vi.mocked(getMyProfile).mockResolvedValue(null);
    expect((await shellProps()).profileComplete).toBeNull();
  });

  it("scores the profile with the You page's checklist", async () => {
    // A new profile: a short bio, a language and a time zone tick nothing on the list.
    vi.mocked(getMyProfile).mockResolvedValue(PROFILE);
    expect((await shellProps()).profileComplete).toBe(0);

    // Two of the eight items: a link and an intent.
    vi.mocked(getMyProfile).mockResolvedValue({
      ...PROFILE,
      links: ["https://a.dev"],
      intents: ["build_together"],
    });
    expect((await shellProps()).profileComplete).toBe(25);
  });

  it.each([500, 503])("keeps the shell on a profile %i", async (status) => {
    vi.mocked(getMyProfile).mockRejectedValue(new ApiError(status, undefined, undefined));
    const props = await shellProps();
    expect(props.profileComplete).toBeNull();
    expect(props.children).toBe(child);
  });

  it.each([
    ["a 400", new ApiError(400, undefined, undefined)],
    ["a 429", new ApiError(429, undefined, undefined)],
    ["a timeout", new DOMException("timed out", "TimeoutError")],
  ])("still throws on %s", async (_, error) => {
    vi.mocked(getMyProfile).mockRejectedValue(error);
    await expect(SignedInLayout({ children: child })).rejects.toBe(error);
  });
});
