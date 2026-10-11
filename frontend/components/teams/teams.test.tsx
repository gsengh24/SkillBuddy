import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SpaceView } from "@/components/spaces/space-view";
import type { Team, TeamInvite, TeamMessage, TeamSpace, TeamSummary } from "@/lib/api/schemas";

import { AskToJoin, MyTeamRequests } from "./ask-to-join";
import { CreateTeam } from "./create-team";
import { FindTeammate, InviteMatchToTeam } from "./find-teammate";
import { InviteLink } from "./invite-link";
import { JoinByLink } from "./join-by-link";
import { MyTeamInvites } from "./my-invites";
import { TeamChat } from "./team-chat";
import { TeamListing } from "./team-listing";
import { SpaceCard } from "./space-card";
import { TeamPeople } from "./team-people";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, refresh: vi.fn() }) }));

const ME = "11111111-0000-4000-8000-000000000001";
const RAVI = "11111111-0000-4000-8000-000000000002";
const MINA = "11111111-0000-4000-8000-000000000003";
const TEAM_ID = "77777777-0000-4000-8000-000000000001";

const SUMMARY: TeamSummary = {
  id: TEAM_ID,
  name: "Hack night",
  purpose: "hackathon",
  description: "48 hours, one app.",
  owner_id: ME,
  member_count: 2,
  max_members: 6,
  created_at: "2026-10-10T10:00:00Z",
  unread: 0,
  last_message_at: null,
  listed: false,
  looking_for: "",
};
const INVITE: TeamInvite = {
  id: "i1",
  kind: "invite",
  status: "pending",
  team: SUMMARY,
  user_id: MINA,
  display_name: "Mina",
  note: "",
  expires_at: "2026-10-24T10:00:00Z",
  created_at: "2026-10-10T10:00:00Z",
};
const TEAM: Team = {
  ...SUMMARY,
  members: [
    { user_id: ME, display_name: "Asha", joined_at: "2026-10-10T10:00:00Z" },
    { user_id: RAVI, display_name: "Ravi", joined_at: "2026-10-10T11:00:00Z" },
  ],
  invites: [INVITE],
  invite_link_expires_at: null,
};
const MESSAGE: TeamMessage = {
  id: "m1",
  team_id: TEAM_ID,
  sender_id: RAVI,
  body: "Kick-off at six?",
  created_at: "2026-10-10T12:00:00Z",
};

function json(status: number, body?: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  push.mockClear();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function lastCall() {
  const [url, init] = fetchMock.mock.calls.at(-1) as [string, RequestInit];
  return {
    url,
    method: init.method,
    body: init.body ? JSON.parse(init.body as string) : undefined,
  };
}

describe("CreateTeam", () => {
  it("makes a pair space and opens it", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(json(201, { ...TEAM, invites: [] }));
    render(<CreateTeam />);
    expect(screen.getByRole("button", { name: "Create pair space" })).toBeDisabled();
    await user.type(screen.getByLabelText("Pair space name"), "Hack night");
    await user.click(screen.getByRole("radio", { name: "Project" }));
    await user.click(screen.getByRole("button", { name: "Create pair space" }));
    expect(lastCall()).toEqual({
      url: "/api/v1/teams",
      method: "POST",
      body: { name: "Hack night", purpose: "project", description: "" },
    });
    expect(push).toHaveBeenCalledWith(`/teams/${TEAM_ID}`);
  });

  it("says why it could not be made", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      json(409, {
        error: { code: "too_many_teams_owned", message: "You own the most pair spaces allowed." },
      }),
    );
    render(<CreateTeam />);
    await user.type(screen.getByLabelText("Pair space name"), "One more");
    await user.click(screen.getByRole("button", { name: "Create pair space" }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });
});

describe("CreateTeam picker and preview", () => {
  it("moves the purpose with the arrow keys and previews the card as you type", async () => {
    const user = userEvent.setup();
    render(<CreateTeam me={{ id: ME, name: "Asha" }} />);
    const group = screen.getByRole("radiogroup", { name: "What is it for?" });
    expect(within(group).getByRole("radio", { name: "Hackathon" })).toBeChecked();
    within(group).getByRole("radio", { name: "Hackathon" }).focus();
    await user.keyboard("{ArrowRight}");
    expect(within(group).getByRole("radio", { name: "Project" })).toBeChecked();
    await user.keyboard("{ArrowLeft}{ArrowLeft}");
    expect(within(group).getByRole("radio", { name: "Other" })).toBeChecked();

    await user.type(screen.getByLabelText("Pair space name"), "Night owls");
    expect(screen.getByText("10 / 60")).toBeInTheDocument();
    // The preview card is hidden from assistive technology and shows the typed name.
    expect(document.querySelector("[aria-hidden] h3")).toHaveTextContent("Night owls");
  });

  it("needs a name of two letters", async () => {
    const user = userEvent.setup();
    render(<CreateTeam />);
    await user.type(screen.getByLabelText("Pair space name"), "A");
    expect(screen.getByRole("button", { name: "Create pair space" })).toBeDisabled();
    await user.type(screen.getByLabelText("Pair space name"), "b");
    expect(screen.getByRole("button", { name: "Create pair space" })).toBeEnabled();
  });
});

describe("SpaceCard", () => {
  it("shows the owner mark, who is in it and goals done, and links in", () => {
    render(
      <SpaceCard
        href={`/teams/${TEAM_ID}`}
        purpose="study"
        name="GATE circle"
        description=""
        isOwner
        people={[{ id: ME, name: "Asha" }]}
        memberCount={2}
        maxMembers={6}
        goals={{ done: 1, total: 4 }}
      />,
    );
    expect(screen.getByRole("link", { name: /GATE circle/ })).toHaveAttribute(
      "href",
      `/teams/${TEAM_ID}`,
    );
    expect(screen.getByText("Study")).toBeInTheDocument();
    expect(screen.getByText("Owner")).toBeInTheDocument();
    expect(screen.getByText("No description yet.")).toBeInTheDocument();
    expect(screen.getByText("2 of 6")).toBeInTheDocument();
    expect(screen.getByText("1 of 4 done")).toBeInTheDocument();
  });

  it("says no goals yet, and leaves the goals row out when they could not load", () => {
    const base = {
      purpose: "project" as const,
      name: "X",
      description: "d",
      isOwner: false,
      people: [],
      memberCount: 1,
      maxMembers: 6,
    };
    const { rerender } = render(<SpaceCard {...base} goals={{ done: 0, total: 0 }} />);
    expect(screen.getByText("No goals yet")).toBeInTheDocument();
    rerender(<SpaceCard {...base} goals={null} />);
    expect(screen.queryByText("Goals")).not.toBeInTheDocument();
    expect(screen.queryByText("Owner")).not.toBeInTheDocument();
  });
});

describe("MyTeamInvites", () => {
  it("shows nothing without invites", () => {
    const { container } = render(<MyTeamInvites initial={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("joins a pair space, or declines and drops the invite", async () => {
    const user = userEvent.setup();
    const other: TeamInvite = { ...INVITE, id: "i2", team: { ...SUMMARY, id: "t2", name: "Lab" } };
    fetchMock.mockResolvedValueOnce(json(200, { ...other, status: "declined" }));
    render(<MyTeamInvites initial={[INVITE, other]} />);
    expect(screen.getAllByText("Hackathon · 2 of 6 people")).toHaveLength(2);
    await user.click(screen.getByRole("button", { name: "Decline the invite to Lab" }));
    expect(lastCall()).toEqual({
      url: "/api/v1/teams/invites/i2/respond",
      method: "POST",
      body: { accept: false },
    });
    expect(screen.queryByText("Lab")).not.toBeInTheDocument();

    fetchMock.mockResolvedValueOnce(json(200, { ...INVITE, status: "accepted" }));
    await user.click(screen.getByRole("button", { name: "Join Hack night" }));
    expect(lastCall().body).toEqual({ accept: true });
    expect(push).toHaveBeenCalledWith(`/teams/${TEAM_ID}`);
  });
});

describe("TeamPeople", () => {
  const invitable = [{ userId: "u9", name: "Kiran" }];

  it("lets the owner invite, take back an invite and remove a member", async () => {
    const user = userEvent.setup();
    render(<TeamPeople team={TEAM} meId={ME} invitable={invitable} />);
    expect(screen.getByText(/owner/)).toBeVisible();
    expect(screen.queryByRole("button", { name: "Remove Asha" })).not.toBeInTheDocument();

    fetchMock.mockResolvedValueOnce(
      json(201, { ...INVITE, id: "i3", user_id: "u9", display_name: "Kiran" }),
    );
    await user.selectOptions(screen.getByLabelText("Invite a connection"), "u9");
    await user.click(screen.getByRole("button", { name: "Send invite" }));
    expect(lastCall()).toEqual({
      url: `/api/v1/teams/${TEAM_ID}/invites`,
      method: "POST",
      body: { user_id: "u9" },
    });
    expect(await screen.findByText("Kiran")).toBeVisible();

    fetchMock.mockResolvedValueOnce(json(204));
    await user.click(screen.getByRole("button", { name: "Take back the invite to Mina" }));
    expect(lastCall()).toMatchObject({ url: "/api/v1/teams/invites/i1", method: "DELETE" });
    expect(screen.queryByText("Mina")).not.toBeInTheDocument();

    fetchMock.mockResolvedValueOnce(json(204));
    await user.click(screen.getByRole("button", { name: "Remove Ravi" }));
    expect(lastCall()).toMatchObject({
      url: `/api/v1/teams/${TEAM_ID}/members/${RAVI}`,
      method: "DELETE",
    });
    expect(screen.queryByText("Ravi")).not.toBeInTheDocument();
  });

  it("gives a member only the way out", async () => {
    const user = userEvent.setup();
    render(<TeamPeople team={{ ...TEAM, invites: [] }} meId={RAVI} invitable={[]} />);
    expect(screen.queryByLabelText("Invite a connection")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^Remove/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Close pair space" })).not.toBeInTheDocument();

    fetchMock.mockResolvedValueOnce(json(204));
    await user.click(screen.getByRole("button", { name: "Leave pair space" }));
    expect(lastCall()).toMatchObject({
      url: `/api/v1/teams/${TEAM_ID}/members/${RAVI}`,
      method: "DELETE",
    });
    expect(push).toHaveBeenCalledWith("/teams");
  });
});

describe("Listed pair spaces", () => {
  const REQUEST: TeamInvite = {
    ...INVITE,
    id: "r1",
    kind: "request",
    user_id: "u9",
    display_name: "Kiran",
    note: "I draw maps.",
  };

  it("lets the owner list the pair space and say who it is looking for", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      json(200, { ...TEAM, invites: [], listed: true, looking_for: "A designer" }),
    );
    render(<TeamListing teamId={TEAM_ID} listed={false} lookingFor="" />);
    expect(screen.getByRole("button", { name: "Save listing" })).toBeDisabled();
    expect(screen.getByText("This pair space is not listed.")).toBeVisible();
    await user.click(screen.getByRole("checkbox", { name: /List this pair space/ }));
    await user.type(screen.getByLabelText("Who are you looking for?"), "A designer");
    await user.click(screen.getByRole("button", { name: "Save listing" }));
    expect(lastCall()).toEqual({
      url: `/api/v1/teams/${TEAM_ID}`,
      method: "PATCH",
      body: { listed: true, looking_for: "A designer" },
    });
    expect(await screen.findByText("This pair space is listed.")).toBeVisible();
  });

  it("sends a request to join with a note", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(json(201, REQUEST));
    render(<AskToJoin teamId={TEAM_ID} teamName="Hack night" asked={false} />);
    await user.click(screen.getByRole("button", { name: "Ask to join Hack night" }));
    await user.type(screen.getByLabelText(/A note to the owner/), "I draw maps.");
    await user.click(screen.getByRole("button", { name: "Send request" }));
    expect(lastCall()).toEqual({
      url: `/api/v1/teams/${TEAM_ID}/requests`,
      method: "POST",
      body: { note: "I draw maps." },
    });
    expect(await screen.findByText(/You asked to join/)).toBeVisible();
  });

  it("shows a request already sent, and takes one back", async () => {
    const user = userEvent.setup();
    render(<AskToJoin teamId={TEAM_ID} teamName="Hack night" asked />);
    expect(screen.getByText(/You asked to join/)).toBeVisible();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();

    fetchMock.mockResolvedValueOnce(json(204));
    render(<MyTeamRequests initial={[REQUEST]} />);
    await user.click(
      screen.getByRole("button", { name: "Take back your request to join Hack night" }),
    );
    expect(lastCall()).toMatchObject({ url: "/api/v1/teams/invites/r1", method: "DELETE" });
    expect(screen.queryByText("Waiting for the owner's answer")).not.toBeInTheDocument();
  });

  it("lets the owner accept a request, which adds the person", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(json(200, { ...REQUEST, status: "accepted" }));
    render(<TeamPeople team={{ ...TEAM, invites: [REQUEST] }} meId={ME} invitable={[]} />);
    expect(screen.getByText(/I draw maps\./)).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Let Kiran join" }));
    expect(lastCall()).toEqual({
      url: "/api/v1/teams/invites/r1/respond",
      method: "POST",
      body: { accept: true },
    });
    expect(await screen.findByRole("button", { name: "Remove Kiran" })).toBeVisible();
    expect(screen.queryByRole("button", { name: "Let Kiran join" })).not.toBeInTheDocument();
  });
});

describe("Finding a teammate", () => {
  it("asks the matcher with the pair space attached, then opens the request", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      json(202, {
        id: "req1",
        text: "A designer who can prototype fast",
        title: "",
        requested_intent: null,
        intent: null,
        status: "pending",
        match_count: 0,
        team_id: TEAM_ID,
        created_at: "2026-10-11T10:00:00Z",
        matched_at: null,
        expires_at: "2026-11-10T10:00:00Z",
      }),
    );
    render(<FindTeammate teamId={TEAM_ID} full={false} />);
    expect(screen.getByRole("button", { name: "Find people" })).toBeDisabled();
    await user.type(
      screen.getByLabelText("Who does the pair space need?"),
      "A designer who can prototype fast",
    );
    await user.click(screen.getByRole("button", { name: "Find people" }));
    expect(lastCall()).toEqual({
      url: "/api/v1/requests",
      method: "POST",
      body: { text: "A designer who can prototype fast", team_id: TEAM_ID },
    });
    expect(push).toHaveBeenCalledTimes(1);
  });

  it("has no form when the pair space is full", () => {
    render(<FindTeammate teamId={TEAM_ID} full />);
    expect(screen.queryByLabelText("Who does the pair space need?")).not.toBeInTheDocument();
    expect(screen.getByText(/The pair space is full/)).toBeVisible();
  });

  it("invites a match to the pair space", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(json(201, { ...INVITE, kind: "suggested" }));
    render(<InviteMatchToTeam teamId={TEAM_ID} matchId="match1" />);
    await user.click(screen.getByRole("button", { name: "Invite to pair space" }));
    expect(lastCall()).toEqual({
      url: `/api/v1/teams/${TEAM_ID}/invites`,
      method: "POST",
      body: { match_id: "match1" },
    });
    expect(await screen.findByText(/Invited to the pair space/)).toBeVisible();
  });
});

describe("InviteLink", () => {
  it("shows a new link once, and turns it off", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      json(201, { code: "abcDEF123456_-abcDEF12", expires_at: "2026-10-17T10:00:00Z" }),
    );
    render(<InviteLink teamId={TEAM_ID} expiresAt={null} full={false} />);
    expect(screen.queryByRole("button", { name: "Turn off link" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Make an invite link" }));
    expect(lastCall()).toMatchObject({
      url: `/api/v1/teams/${TEAM_ID}/invite-link`,
      method: "POST",
    });
    expect(await screen.findByLabelText("Link to share")).toHaveValue(
      `${window.location.origin}/teams/join/abcDEF123456_-abcDEF12`,
    );
    expect(screen.getByText(/You won't be shown this link again/)).toBeVisible();

    fetchMock.mockResolvedValueOnce(json(204));
    await user.click(screen.getByRole("button", { name: "Turn off link" }));
    expect(lastCall()).toMatchObject({ method: "DELETE" });
    expect(screen.queryByLabelText("Link to share")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Make an invite link" })).toBeVisible();
  });

  it("says a link is active without showing it", () => {
    render(<InviteLink teamId={TEAM_ID} expiresAt="2026-10-17T10:00:00Z" full />);
    expect(screen.getByText(/A link is active until/)).toBeVisible();
    expect(screen.getByText("The pair space is full, so nobody can join.")).toBeVisible();
    expect(screen.queryByLabelText("Link to share")).not.toBeInTheDocument();
  });
});

describe("JoinByLink", () => {
  it("joins and opens the pair space", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(json(200, { ...TEAM, invites: [] }));
    render(<JoinByLink code="abcDEF123456_-abcDEF12" teamName="Hack night" />);
    await user.click(screen.getByRole("button", { name: "Join Hack night" }));
    expect(lastCall()).toMatchObject({
      url: "/api/v1/teams/join/abcDEF123456_-abcDEF12",
      method: "POST",
    });
    expect(push).toHaveBeenCalledWith(`/teams/${TEAM_ID}`);
  });

  it("says when the link no longer works", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      json(404, {
        error: { code: "team_link_invalid", message: "This invite link doesn't work any more." },
      }),
    );
    render(<JoinByLink code="abcDEF123456_-abcDEF12" teamName="Hack night" />);
    await user.click(screen.getByRole("button", { name: "Join Hack night" }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(push).not.toHaveBeenCalled();
  });
});

describe("TeamChat", () => {
  function renderChat(initial: TeamMessage[] = [MESSAGE]) {
    return render(
      <TeamChat
        teamId={TEAM_ID}
        teamName="Hack night"
        meId={ME}
        names={{ [ME]: "Asha", [RAVI]: "Ravi" }}
        initial={initial}
        cursor="c0"
        retentionDays={90}
        hasUnread={false}
      />,
    );
  }

  it("names who said what and says the whole pair space can read it", () => {
    const gone: TeamMessage = { ...MESSAGE, id: "m0", sender_id: MINA, body: "Bye all" };
    renderChat([MESSAGE, gone]);
    const rows = within(screen.getByRole("list", { name: "Messages" })).getAllByRole("listitem");
    expect(rows[0]).toHaveTextContent("A teammate"); // someone who has left
    expect(rows[1]).toHaveTextContent("Ravi");
    expect(rows[1]).toHaveTextContent("Kick-off at six?");
    expect(screen.getByText(/Everyone in the pair space can read this/)).toBeVisible();
    // Other people's messages can be reported; there are two here.
    expect(screen.getAllByRole("button", { name: "Report" })).toHaveLength(2);
  });

  it("sends a message to the pair space", async () => {
    const user = userEvent.setup();
    const sent: TeamMessage = { ...MESSAGE, id: "m2", sender_id: ME, body: "Works for me" };
    fetchMock.mockResolvedValue(json(201, sent));
    renderChat();
    await user.type(screen.getByLabelText("Message Hack night"), "Works for me");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(fetchMock.mock.calls[0]?.[0]).toBe(`/api/v1/teams/${TEAM_ID}/messages`);
    expect(await screen.findByText("Works for me")).toBeVisible();
  });
});

describe("SpaceView for a pair space", () => {
  const SPACE: TeamSpace = {
    team_id: TEAM_ID,
    goals: [
      {
        id: "g1",
        title: "Ship the demo",
        status: "open",
        due_on: null,
        done_at: null,
        created_by: RAVI,
        created_at: "2026-10-10T10:00:00Z",
      },
    ],
    skills: [
      { id: "s1", name: "Figma", owner_id: RAVI, created_at: "2026-10-10T10:00:00Z" },
      { id: "s2", name: "Go", owner_id: MINA, created_at: "2026-10-10T10:00:00Z" },
    ],
    logs: [
      {
        id: "l1",
        note: "Drew the screens",
        author_id: RAVI,
        goal_id: null,
        skill_id: null,
        created_at: "2026-10-10T11:00:00Z",
      },
    ],
    retention_days: 90,
    max_goals: 30,
    max_skills_per_person: 10,
  };

  it("groups skills by teammate, names note authors and uses the pair space's API path", async () => {
    const user = userEvent.setup();
    render(
      <SpaceView
        space={SPACE}
        meId={ME}
        team={{ base: `/teams/${TEAM_ID}/space`, names: { [RAVI]: "Ravi" } }}
      />,
    );
    expect(screen.getByRole("heading", { name: "Ravi" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "A teammate" })).toBeVisible(); // Mina has left
    const notes = within(screen.getByRole("list", { name: "Progress notes" })).getAllByRole(
      "listitem",
    );
    expect(notes[0]).toHaveTextContent("Ravi");
    // A teammate's goal and note can be reported, like in a pair space.
    expect(screen.getAllByRole("button", { name: "Report" })).toHaveLength(2);

    fetchMock.mockResolvedValueOnce(json(201, { ...SPACE.goals[0], id: "g2", title: "Pitch" }));
    await user.type(screen.getByLabelText("New goal"), "Pitch");
    await user.click(screen.getByRole("button", { name: "Add goal" }));
    expect(lastCall().url).toBe(`/api/v1/teams/${TEAM_ID}/space/goals`);
  });
});
