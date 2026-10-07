import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MatchCard } from "@/components/discover/match-card";
import { BlockButton } from "@/components/safety/block-button";
import { ReportButton } from "@/components/safety/report-button";
import { IntroCard } from "@/components/social/intro-card";
import type { Match, Message } from "@/lib/api/schemas";
import { intro } from "@/lib/home/fixtures";

import { Conversation } from "./conversation";

/*
 * Keyboard and screen-reader checks on the restyled match card, intro, chat, block and
 * report controls (PR 4). Wording and behaviour are covered by the existing tests.
 */

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }) }));
vi.mock("@/lib/api/browser", () => ({ browserApi: vi.fn(() => new Promise(() => undefined)) }));

const MATCH: Match = {
  id: "match-1",
  rank: 1,
  reason: "You both build budgeting tools.",
  status: "shown",
  candidate: {
    user_id: "22222222-0000-4000-8000-000000000002",
    summary: "Final-year design student.",
    offers: ["UI design"],
    seeks: [],
    interests: ["Chess"],
    availability: "Weekends",
    languages: ["English"],
  },
};

const ME = "me";
const THEM = "them";
const MESSAGES: Message[] = [
  {
    id: "2",
    connection_id: "c",
    sender_id: ME,
    body: "Friday works.",
    created_at: "2026-10-07T10:05:00Z",
  },
  {
    id: "1",
    connection_id: "c",
    sender_id: THEM,
    body: "Hello!",
    created_at: "2026-10-07T10:00:00Z",
  },
];

beforeEach(() => {
  vi.useRealTimers();
});

describe("match card", () => {
  it("opens and cancels the intro form from the keyboard, with a labelled note", async () => {
    render(<MatchCard match={MATCH} />);
    const user = userEvent.setup();
    const send = screen.getByRole("button", { name: "Send intro" });
    send.focus();
    await user.keyboard("{Enter}");
    const note = screen.getByLabelText("A short hello (optional)");
    expect(note).toHaveAccessibleDescription(/0\/500 characters/);
    // Opening the form doesn't move focus into it (unchanged behaviour; noted in the PR).
    note.focus();
    await user.tab();
    expect(screen.getByRole("button", { name: "Send intro" })).toHaveFocus();
    await user.tab();
    const cancel = screen.getByRole("button", { name: "Cancel" });
    expect(cancel).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(screen.queryByLabelText("A short hello (optional)")).not.toBeInTheDocument();
  });

  it("names the match and keeps the person's dot out of the accessibility tree", () => {
    const { container } = render(<MatchCard match={MATCH} />);
    expect(screen.getByRole("heading", { name: "Final-year design student." })).toBeInTheDocument();
    expect(container.querySelector('[aria-hidden="true"]')).not.toBeNull();
    expect(screen.getByRole("button", { name: "Report" })).toBeInTheDocument();
  });
});

describe("received intro", () => {
  it("is an article named by its heading, with Accept and Decline reachable by Tab", async () => {
    render(<IntroCard initial={intro()} />);
    const card = screen.getByRole("article", { name: "Someone wants to meet you" });
    const user = userEvent.setup();
    await user.tab();
    expect(within(card).getByRole("button", { name: "Accept" })).toHaveFocus();
    await user.tab();
    expect(within(card).getByRole("button", { name: "Decline" })).toHaveFocus();
  });
});

describe("chat", () => {
  it("labels the message list and says who wrote each bubble", () => {
    render(
      <Conversation
        connectionId="c"
        meId={ME}
        otherId={THEM}
        otherName="Asha"
        initial={MESSAGES}
        cursor="cursor"
        retentionDays={90}
        hasUnread={false}
      />,
    );
    const list = screen.getByRole("list", { name: "Messages" });
    expect(within(list).getByText(/Asha:/)).toHaveClass("sr-only");
    expect(within(list).getByText(/You:/)).toHaveClass("sr-only");
    expect(screen.getByLabelText("Message Asha")).toBeInTheDocument();
  });
});

describe("block and report", () => {
  it("block: the confirm panel is a named group, and Cancel works from the keyboard", async () => {
    render(<BlockButton userId="u" name="Asha" />);
    const user = userEvent.setup();
    screen.getByRole("button", { name: "Block" }).focus();
    await user.keyboard("{Enter}");
    expect(screen.getByRole("group", { name: "Block Asha?" })).toBeInTheDocument();
    screen.getByRole("button", { name: "Cancel" }).focus();
    await user.keyboard(" ");
    expect(screen.queryByRole("group")).not.toBeInTheDocument();
  });

  it("report: the form is named, reasons are radios chosen from the keyboard", async () => {
    render(<ReportButton kind="message" targetId="m" />);
    const user = userEvent.setup();
    screen.getByRole("button", { name: "Report" }).focus();
    await user.keyboard("{Enter}");
    const form = screen.getByRole("form", { name: "Report this message" });
    const first = within(form).getAllByRole("radio")[0] as HTMLElement;
    first.focus();
    await user.keyboard(" ");
    expect(first).toBeChecked();
    expect(within(form).getByRole("button", { name: "Send report" })).toBeEnabled();
  });
});
