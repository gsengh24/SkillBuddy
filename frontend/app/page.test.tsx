import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import LandingPage, { metadata } from "./page";

vi.mock("@/components/api-status", () => ({
  ApiStatusIndicator: () => <div role="status" data-state="connected" />,
  ApiStatusFallback: () => null,
}));

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("landing page", () => {
  it("shows the hero, how it works, the three cards, the FAQ, the CTA and the footer", () => {
    render(<LandingPage />);
    expect(
      screen.getByRole("heading", { level: 1, name: /Say what you're building\./ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: /Skills\. Interests\. Intent\./ }),
    ).toBeInTheDocument();
    for (const label of ["Safe by default", "Human chats", "Pair spaces"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    expect(screen.getByRole("heading", { name: /Questions,/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /Your next collaborator/ })).toBeInTheDocument();
    expect(screen.getByText("© 2026 Cynergi")).toBeInTheDocument();
    // Smoke checks that the page shows the API status.
    expect(document.querySelector('[data-state="connected"]')).not.toBeNull();
  });

  it("links to sign in, the sections, and the legal pages", () => {
    render(<LandingPage />);
    for (const name of ["Get started", "Sign in"]) {
      expect(screen.getByRole("link", { name })).toHaveAttribute("href", "/login");
    }
    for (const link of screen.getAllByRole("link", { name: "Find your people" })) {
      expect(link).toHaveAttribute("href", "/login");
    }
    expect(screen.getByRole("link", { name: "See how it works" })).toHaveAttribute("href", "#how");
    const footer = screen.getByRole("contentinfo");
    expect(within(footer).getByRole("link", { name: "Privacy" })).toHaveAttribute(
      "href",
      "/privacy",
    );
    expect(within(footer).getByRole("link", { name: "Terms" })).toHaveAttribute("href", "/terms");
    expect(within(footer).getByRole("link", { name: "Contact us" }).getAttribute("href")).toMatch(
      /^mailto:/,
    );
  });

  it("opens FAQ answers with aria-expanded", async () => {
    render(<LandingPage />);
    const question = screen.getByRole("button", { name: "Does AI read my chats?" });
    expect(question).toHaveAttribute("aria-expanded", "false");
    await userEvent.setup().click(question);
    expect(question).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("region", { name: "Does AI read my chats?" })).toHaveTextContent(
      "We don't use AI to read your chat messages.",
    );
  });

  it("keeps the copy within what the privacy page says", () => {
    const { container } = render(<LandingPage />);
    const text = container.textContent ?? "";
    expect(text).toContain("Block or report from any chat.");
    expect(text).not.toMatch(/one tap/i);
    expect(text).not.toMatch(/All rights reserved/i);
    expect(text).not.toMatch(/testimonial|pricing/i);
  });

  it("shows sections at once with reduced motion", () => {
    let fire: (entries: { isIntersecting: boolean }[]) => void = () => undefined;
    vi.stubGlobal(
      "IntersectionObserver",
      class {
        constructor(callback: typeof fire) {
          fire = callback;
        }
        observe() {}
        disconnect() {}
      },
    );
    vi.stubGlobal("matchMedia", () => ({ matches: true }));
    const { container } = render(<LandingPage />);
    act(() => fire([{ isIntersecting: false }]));
    for (const section of container.querySelectorAll("[data-motion]")) {
      expect(section).toHaveAttribute("data-motion", "static");
    }
  });

  it("has a title, description, canonical and Open Graph data", () => {
    expect(metadata.title).toEqual({ absolute: expect.stringContaining("Cynergi") });
    expect(metadata.description).toBeTruthy();
    expect(metadata.alternates).toEqual({ canonical: "/" });
    expect(metadata.openGraph).toMatchObject({ type: "website", siteName: "Cynergi" });
  });
});
