import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PrivacyPage from "@/app/privacy/page";
import TermsPage from "@/app/terms/page";
import { EmailToggle } from "@/components/profile/email-toggle";
import { legal } from "@/lib/legal";

describe("privacy policy", () => {
  it("has the AI section at #ai, the retention rules and the contact address", () => {
    const { container } = render(<PrivacyPage />);

    const ai = container.querySelector("#ai");
    expect(ai).not.toBeNull();
    expect(ai).toHaveTextContent("currently Groq, Inc., with Cloudflare, Inc. as a backup");
    expect(ai).toHaveTextContent("We never send your name, email address or contact details");
    expect(container.querySelector("#messages")).toHaveTextContent(
      "Each message is deleted 90 days after it's sent",
    );
    expect(container.querySelector("#reports")).toHaveTextContent(
      "deleted 180 days after the report is resolved",
    );
    expect(container.querySelector("#reports")).toHaveTextContent("a goal or note in a pair space");
    expect(container.querySelector("#retention")).toHaveTextContent(
      "Pair-space progress notes: 90 days after each is written",
    );
    expect(container.querySelector("#retention")).toHaveTextContent(
      "hidden from both people as soon as the connection ends, and deleted 90 days later",
    );
    expect(container.querySelector("#who-sees")).toHaveTextContent(
      "can be seen only by the two people in it",
    );
    expect(container.querySelector("#emails")).toHaveTextContent(
      "We email you when someone sends you an intro or accepts yours",
    );
    expect(screen.getAllByRole("link", { name: legal.contactEmail })[0]).toHaveAttribute(
      "href",
      `mailto:${legal.contactEmail}`,
    );
    expect(screen.getByText(/Draft, pending legal review/)).toBeVisible();
  });
});

describe("terms", () => {
  it("lists what isn't allowed, blocking and moderation", () => {
    const { container } = render(<TermsPage />);
    expect(container.querySelector("#conduct")).toHaveTextContent(
      "run scams or ask people for money",
    );
    expect(container.querySelector("#blocking")).toHaveTextContent("the old chat stays closed");
    expect(container.querySelector("#reporting")).toHaveTextContent("We may suspend accounts");
    expect(screen.getByRole("link", { name: legal.contactEmail })).toBeInTheDocument();
  });
});

describe("EmailToggle", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("turns intro emails off, and back if saving fails", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          error: { code: "storage_full", message: "x", request_id: null, details: null },
        }),
        { status: 503, headers: { "Content-Type": "application/json" } },
      ),
    );
    render(<EmailToggle initial />);
    const toggle = screen.getByRole("switch", { name: /Emails about intros/ });
    expect(toggle).toBeChecked();

    await user.click(toggle);

    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/me/profile");
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body as string)).toEqual({ email_notifications: false });
    expect(await screen.findByRole("alert")).toHaveTextContent("can't save changes");
    expect(toggle).toBeChecked();
  });
});

describe("the product name on the legal pages", () => {
  it.each([
    ["privacy", PrivacyPage],
    ["terms", TermsPage],
  ])("the %s page says Cynergi and never the old name", (_name, Page) => {
    const { container } = render(<Page />);
    const text = container.textContent ?? "";
    expect(text).toContain("Cynergi");
    expect(text).not.toMatch(/Skill ?Buddy|skill-buddy|skillbuddy/i);
  });

  it("keeps a table of contents that points at every section", () => {
    for (const Page of [PrivacyPage, TermsPage]) {
      const { container, unmount } = render(<Page />);
      const toc = screen.getByRole("navigation", { name: "On this page" });
      for (const link of toc.querySelectorAll("a")) {
        const id = link.getAttribute("href")?.slice(1) ?? "";
        expect(container.querySelector(`section#${id}`)).not.toBeNull();
      }
      unmount();
    }
  });
});
