import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { profileSchema } from "@/lib/api/schemas";

import { YouPage } from "./you-page";

const router = { replace: vi.fn(), refresh: vi.fn(), push: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router }));

const PROFILE = profileSchema.parse({
  user_id: "8d3f4b2a-0000-4000-8000-000000000001",
  display_name: "Meera Iyer",
  about_text: "I design mobile apps and want to ship something of my own, on weekends.",
  links: ["https://github.com/meera", "https://meera.design"],
  timezone: "Asia/Kolkata",
  languages: ["en"],
  visibility: "matchable",
  email_notifications: true,
  city: "Bengaluru",
  headline: "Product designer learning to code",
  intents: ["build_together"],
  available_days: ["sat"],
  available_from: "18:00:00",
  parse_status: "parsed",
  parse_source: "template",
  understanding: {
    summary: "Designs mobile apps.",
    offers: ["UI design"],
    seeks: ["React"],
    interests: ["chess"],
    availability: "weekends",
  },
  ai_consent_version: "2026-10-01",
  ai_consent_at: "2026-10-02T10:00:00Z",
  ai_consent_current: true,
  created_at: "2026-10-02T10:00:00Z",
  updated_at: "2026-10-02T10:00:00Z",
});

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn(async () => json(200, PROFILE));
  vi.stubGlobal("fetch", fetchMock);
  router.refresh.mockReset();
  document.cookie = "csrf_token=csrf-value-123; path=/";
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderPage(profile = PROFILE) {
  return render(
    <YouPage
      profile={profile}
      email="meera@example.com"
      termsVersion="2026-10-08-draft"
      isModerator={false}
    />,
  );
}

function calls() {
  return fetchMock.mock.calls.map(([url, init]) => [
    String(url),
    (init as RequestInit).method,
    JSON.parse(String((init as RequestInit).body ?? "null")),
  ]);
}

describe("YouPage", () => {
  it("loads the profile into ten sections, in the reference's order", () => {
    renderPage();
    expect(screen.getByRole("heading", { level: 1, name: /Your profile\./ })).toBeInTheDocument();
    const nav = screen.getByRole("navigation", { name: "Sections" });
    expect(
      within(nav)
        .getAllByRole("link")
        .map((a) => a.textContent),
    ).toEqual([
      "01Basics",
      "02Skills",
      "03Looking for",
      "04Availability",
      "05Links",
      "06Privacy",
      "07Alerts",
      "08Security",
      "09Your data",
      "10Danger zone",
    ]);
    expect(screen.getByLabelText("Headline")).toHaveValue("Product designer learning to code");
    expect(screen.getByLabelText("City")).toHaveValue("Bengaluru");
    expect(screen.getByLabelText("From")).toHaveValue("18:00");
    // Each link sits in the row for its site.
    expect(screen.getByLabelText("GitHub")).toHaveValue("https://github.com/meera");
    expect(screen.getByLabelText("Portfolio")).toHaveValue("https://meera.design");
    expect(screen.getByRole("button", { name: "Build together" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: "Saturday" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("meter", { name: "Profile strength" })).toHaveAttribute(
      "aria-valuenow",
      // 5 of 8: no longer bio, fewer than 3 skills offered, no goal yet.
      "63",
    );
    // Nothing changed yet: no Save bar.
    expect(screen.queryByRole("region", { name: "Unsaved changes" })).not.toBeInTheDocument();
  });

  it("shows the Save bar after a change, and saves it with one call", async () => {
    const user = userEvent.setup({ delay: null });
    renderPage();
    const headline = screen.getByLabelText("Headline");
    await user.clear(headline);
    await user.type(headline, "Designer who ships");

    const bar = screen.getByRole("region", { name: "Unsaved changes" });
    await user.click(within(bar).getByRole("button", { name: "Save changes" }));

    expect(calls()).toEqual([["/api/v1/me/profile", "PATCH", { headline: "Designer who ships" }]]);
    expect(router.refresh).toHaveBeenCalledOnce();
    expect(screen.queryByRole("region", { name: "Unsaved changes" })).not.toBeInTheDocument();
    expect(screen.getByText("Saved.")).toBeInTheDocument();
  });

  it("discards back to what was saved", async () => {
    const user = userEvent.setup({ delay: null });
    renderPage();
    await user.type(screen.getByLabelText("City"), " North");
    await user.click(screen.getByRole("button", { name: "Explore" }));
    await user.click(screen.getByRole("button", { name: "Discard" }));

    expect(screen.getByLabelText("City")).toHaveValue("Bengaluru");
    expect(screen.getByRole("button", { name: "Explore" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    expect(screen.queryByRole("region", { name: "Unsaved changes" })).not.toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("keeps the edits when a save fails, and says what happened", async () => {
    fetchMock.mockResolvedValueOnce(
      json(429, { error: { code: "rate_limited", message: "x", request_id: null, details: null } }),
    );
    const user = userEvent.setup({ delay: null });
    renderPage();
    await user.type(screen.getByLabelText("Your goal right now"), "Ship by December.");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByLabelText("Your goal right now")).toHaveValue("Ship by December.");
    expect(screen.getByRole("region", { name: "Unsaved changes" })).toBeInTheDocument();
    expect(router.refresh).not.toHaveBeenCalled();
  });

  it("saves skills as a correction, and a new description with PUT", async () => {
    const user = userEvent.setup({ delay: null });
    renderPage();
    await user.type(
      screen.getByRole("textbox", { name: "Add a skill you can offer" }),
      "Figma{Enter}",
    );
    await user.click(screen.getByRole("button", { name: "Remove React" }));
    await user.type(screen.getByLabelText("About you"), " Also into chess.");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    const [put, understanding] = calls();
    expect(put?.slice(0, 2)).toEqual(["/api/v1/me/profile", "PUT"]);
    expect(put?.[2]).toMatchObject({
      about_text: `${PROFILE.about_text} Also into chess.`,
      visibility: "matchable",
      links: ["https://meera.design", "https://github.com/meera"],
    });
    expect(understanding).toEqual([
      "/api/v1/me/profile/understanding",
      "PUT",
      {
        summary: "Designs mobile apps.",
        offers: ["UI design", "Figma"],
        seeks: [],
        interests: ["chess"],
        availability: "weekends",
      },
    ]);
    expect(calls()).toHaveLength(2);
  });

  it("asks for AI consent again when the description changes and it is out of date", async () => {
    const user = userEvent.setup({ delay: null });
    renderPage({ ...PROFILE, ai_consent_current: false });
    expect(screen.queryByRole("checkbox", { name: /read by AI/ })).not.toBeInTheDocument();
    await user.type(screen.getByLabelText("About you"), " More.");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/agree to how AI is used/);
    expect(fetchMock).not.toHaveBeenCalled();
    await user.click(screen.getByRole("checkbox", { name: /read by AI/ }));
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(calls()[0]?.[2]).toMatchObject({ ai_consent: true });
  });

  it("previews the card others see, with the edits so far", async () => {
    const user = userEvent.setup({ delay: null });
    renderPage();
    const city = screen.getByLabelText("City");
    await user.clear(city);
    await user.type(city, "Chennai");
    await user.click(screen.getByRole("button", { name: "See how others see you" }));

    const dialog = screen.getByRole("dialog", { name: "How others see you" });
    expect(dialog).toHaveTextContent("Chennai");
    expect(dialog).toHaveTextContent("UI design");
    expect(dialog).toHaveTextContent("Designs mobile apps.");
    // Names and links come only with a connection.
    expect(dialog).not.toHaveTextContent("Meera Iyer");
    expect(dialog).toHaveTextContent(/name and links appear only once you're connected/);

    await user.click(within(dialog).getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog", { name: "How others see you" })).not.toBeInTheDocument();
  });

  it("hides the city from the preview when location is hidden", async () => {
    const user = userEvent.setup({ delay: null });
    renderPage();
    await user.click(
      within(screen.getByRole("group", { name: "Location shown as" })).getByRole("button", {
        name: "Hidden",
      }),
    );
    await user.click(screen.getByRole("button", { name: "See how others see you" }));
    expect(screen.getByRole("dialog", { name: "How others see you" })).not.toHaveTextContent(
      "Bengaluru",
    );
  });

  it("keeps the existing legal links, switches and account actions", () => {
    renderPage();
    expect(screen.getByRole("link", { name: "Blocked people" })).toHaveAttribute(
      "href",
      "/settings/blocked",
    );
    expect(screen.getByRole("link", { name: "Terms" })).toHaveAttribute("href", "/terms");
    expect(screen.getByRole("link", { name: "Privacy policy" })).toHaveAttribute(
      "href",
      "/privacy",
    );
    expect(screen.getByText("You accepted version 2026-10-08-draft.")).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: /Show me in new matches/ })).toBeChecked();
    expect(screen.getByRole("switch", { name: /Emails about intros/ })).toBeChecked();
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete my account…" })).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveAttribute("readonly");
    // Section numbers are decoration only.
    expect(screen.getByRole("heading", { name: "Danger zone" })).toBeInTheDocument();
  });

  it("reaches the section links from the keyboard", async () => {
    const user = userEvent.setup({ delay: null });
    renderPage();
    const first = screen.getByRole("link", { name: /Basics/ });
    first.focus();
    await user.tab();
    expect(screen.getByRole("link", { name: /Skills/ })).toHaveFocus();
    expect(first).toHaveAttribute("aria-current", "location");
  });
});
