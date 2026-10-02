import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AppNotification, Intro, Match } from "@/lib/api/schemas";

import { IntroCard } from "./intro-card";
import { NotificationList } from "./notification-list";
import { SendIntro } from "./send-intro";

const PERSON = {
  user_id: "33333333-0000-4000-8000-000000000001",
  display_name: null,
  links: null,
  summary: "Final-year design student.",
  offers: ["UI design"],
  seeks: [],
  interests: ["chess"],
  availability: "weekends",
  languages: ["en"],
};
const INTRO: Intro = {
  id: "44444444-0000-4000-8000-000000000001",
  direction: "received",
  status: "pending",
  note: "Hi! Want to build a budgeting app?",
  request_text: "A designer for my budgeting app.",
  reason: "You offer UI design, which they are looking for.",
  person: PERSON,
  created_at: "2026-10-03T10:00:00Z",
  expires_at: "2026-10-17T10:00:00Z",
  responded_at: null,
};
const MATCH: Match = {
  id: "22222222-0000-4000-8000-000000000001",
  rank: 1,
  reason: "They offer UI design.",
  status: "shown",
  candidate: { ...PERSON, seeks: [] },
};

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("SendIntro", () => {
  it("explains what the other person sees, then sends the note", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(json(201, { ...INTRO, direction: "sent" }));
    render(<SendIntro match={MATCH} hue="green" />);

    await user.click(screen.getByRole("button", { name: "Send intro" }));
    expect(screen.getByText(/Your name and links stay hidden unless they accept/)).toBeVisible();
    await user.type(screen.getByLabelText("A short hello (optional)"), "  Hello there  ");
    await user.click(screen.getByRole("button", { name: "Send intro" }));

    expect(fetchMock.mock.calls[0]?.[0]).toBe(`/api/v1/matches/${MATCH.id}/intro`);
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(JSON.parse(init.body as string)).toEqual({ note: "Hello there" });
    expect(await screen.findByText(/Intro sent/)).toBeInTheDocument();
  });

  it("shows the state of an intro already sent or accepted", () => {
    const { rerender } = render(
      <SendIntro match={{ ...MATCH, status: "intro_sent" }} hue="green" />,
    );
    expect(screen.getByText(/Intro sent/)).toBeInTheDocument();
    rerender(<SendIntro match={{ ...MATCH, status: "accepted" }} hue="green" />);
    expect(screen.getByRole("link", { name: "Open Messages" })).toHaveAttribute(
      "href",
      "/messages",
    );
  });

  it("shows API errors", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      json(409, { error: { code: "intro_exists", message: "x", request_id: null, details: null } }),
    );
    render(<SendIntro match={MATCH} hue="green" />);
    await user.click(screen.getByRole("button", { name: "Send intro" }));
    await user.click(screen.getByRole("button", { name: "Send intro" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("already an intro between you two");
  });
});

describe("IntroCard", () => {
  it("shows the request, reason and note without a name", () => {
    render(<IntroCard initial={INTRO} />);
    expect(screen.getByRole("heading", { name: "Someone wants to meet you" })).toBeInTheDocument();
    expect(screen.getByText(/A designer for my budgeting app/)).toBeInTheDocument();
    expect(screen.getByText(INTRO.reason)).toBeInTheDocument();
    expect(screen.getByText(INTRO.note)).toBeInTheDocument();
    expect(screen.getByText(/they won't be told/)).toBeInTheDocument();
  });

  it("accepting reveals the name and links", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      json(200, {
        ...INTRO,
        status: "accepted",
        person: { ...PERSON, display_name: "Asha", links: ["https://github.com/asha"] },
      }),
    );
    render(<IntroCard initial={INTRO} />);
    await user.click(screen.getByRole("button", { name: "Accept" }));

    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(JSON.parse(init.body as string)).toEqual({ accept: true });
    expect(
      await screen.findByRole("heading", { name: "Asha wants to meet you" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "https://github.com/asha" })).toBeInTheDocument();
  });

  it("declining says it stays private", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(json(200, { ...INTRO, status: "declined" }));
    render(<IntroCard initial={INTRO} />);
    await user.click(screen.getByRole("button", { name: "Decline" }));
    expect(await screen.findByText(/Declined. They won't be told./)).toBeInTheDocument();
  });
});

describe("NotificationList", () => {
  const ITEMS: AppNotification[] = [
    {
      id: "n1",
      kind: "intro_received",
      intro_id: INTRO.id,
      request_id: null,
      read_at: null,
      created_at: "2026-10-03T10:00:00Z",
    },
    {
      id: "n2",
      kind: "matches_ready",
      intro_id: null,
      request_id: "r1",
      read_at: "2026-10-03T11:00:00Z",
      created_at: "2026-10-03T09:00:00Z",
    },
  ];

  it("words each kind and marks everything read", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(json(200, { marked: 1 }));
    render(<NotificationList initial={ITEMS} unread={1} />);
    expect(screen.getByText("Someone sent you an intro.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open Discover" })).toHaveAttribute("href", "/home");
    expect(screen.getByText("1 unread")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Mark all as read" }));
    expect(await screen.findByText("All read")).toBeInTheDocument();
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/notifications/read");
  });

  it("says when there is nothing", () => {
    render(<NotificationList initial={[]} unread={0} />);
    expect(screen.getByText("Nothing yet.")).toBeInTheDocument();
  });
});
