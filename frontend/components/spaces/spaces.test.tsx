import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Goal, ProgressLog, Skill, Space } from "@/lib/api/schemas";

import { SpaceView } from "./space-view";

const ME = "11111111-0000-4000-8000-000000000001";
const THEM = "11111111-0000-4000-8000-000000000002";
const CONNECTION = "55555555-0000-4000-8000-000000000001";
const BASE = `/api/v1/connections/${CONNECTION}/space`;

const GOAL: Goal = {
  id: "g1",
  title: "Ship the MVP",
  status: "open",
  due_on: "2026-12-01",
  done_at: null,
  created_by: ME,
  created_at: "2026-10-04T10:00:00Z",
};
const MY_SKILL: Skill = {
  id: "s1",
  name: "Python",
  owner_id: ME,
  created_at: "2026-10-04T10:00:00Z",
};
const THEIR_SKILL: Skill = {
  id: "s2",
  name: "Figma",
  owner_id: THEM,
  created_at: "2026-10-04T10:00:00Z",
};
const MY_LOG: ProgressLog = {
  id: "l1",
  note: "Wrote the sign-up page",
  author_id: ME,
  goal_id: "g1",
  skill_id: null,
  created_at: "2026-10-04T11:00:00Z",
};
const THEIR_LOG: ProgressLog = {
  ...MY_LOG,
  id: "l2",
  note: "Drew the screens",
  author_id: THEM,
  goal_id: null,
};

function space(overrides: Partial<Space> = {}): Space {
  return {
    connection_id: CONNECTION,
    goals: [GOAL],
    skills: [MY_SKILL, THEIR_SKILL],
    logs: [THEIR_LOG, MY_LOG],
    retention_days: 90,
    max_goals: 30,
    max_skills_per_person: 10,
    ...overrides,
  };
}

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
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderSpace(initial = space()) {
  return render(<SpaceView space={initial} meId={ME} otherId={THEM} otherName="Asha" />);
}

function lastCall() {
  const [url, init] = fetchMock.mock.calls.at(-1) as [string, RequestInit];
  return {
    url,
    method: init.method,
    body: init.body ? JSON.parse(init.body as string) : undefined,
  };
}

describe("SpaceView", () => {
  it("shows the goals, both people's skills and the notes", () => {
    renderSpace();
    expect(screen.getByRole("checkbox", { name: /Ship the MVP/ })).not.toBeChecked();
    expect(screen.getByText(/due 2026-12-01/)).toBeVisible();
    expect(screen.getByText("Python")).toBeVisible();
    expect(screen.getByText("Figma")).toBeVisible();
    const notes = within(screen.getByRole("list", { name: "Progress notes" })).getAllByRole(
      "listitem",
    );
    expect(notes[0]).toHaveTextContent("Asha");
    expect(notes[0]).toHaveTextContent("Drew the screens");
    expect(notes[1]).toHaveTextContent("You");
    expect(notes[1]).toHaveTextContent("Ship the MVP"); // what the note is about
  });

  it("only offers to remove your own skills and notes", () => {
    renderSpace();
    expect(screen.getByRole("button", { name: "Remove Python" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Remove Figma" })).not.toBeInTheDocument();
    const notes = within(screen.getByRole("list", { name: "Progress notes" })).getAllByRole(
      "listitem",
    );
    expect(within(notes[0]!).queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
    expect(within(notes[1]!).getByRole("button", { name: "Delete" })).toBeInTheDocument();
  });

  it("adds a goal with a due date, and marks it done", async () => {
    const user = userEvent.setup();
    const added: Goal = { ...GOAL, id: "g2", title: "Launch", due_on: "2026-11-01" };
    fetchMock
      .mockResolvedValueOnce(json(201, added))
      .mockResolvedValueOnce(
        json(200, { ...added, status: "done", done_at: "2026-10-05T10:00:00Z" }),
      );
    renderSpace(space({ goals: [] }));

    await user.type(screen.getByLabelText("New goal"), "  Launch  ");
    await user.type(screen.getByLabelText("Due date (optional)"), "2026-11-01");
    await user.click(screen.getByRole("button", { name: "Add goal" }));
    expect(lastCall()).toEqual({
      url: `${BASE}/goals`,
      method: "POST",
      body: { title: "Launch", due_on: "2026-11-01" },
    });

    await user.click(await screen.findByRole("checkbox", { name: /Launch/ }));
    expect(lastCall()).toEqual({
      url: `${BASE}/goals/g2`,
      method: "PATCH",
      body: { status: "done" },
    });
    expect(await screen.findByRole("checkbox", { name: /Launch/ })).toBeChecked();
  });

  it("writes a note about one of your skills", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      json(201, { ...MY_LOG, id: "l3", note: "Finished a course", goal_id: null, skill_id: "s1" }),
    );
    renderSpace();

    await user.type(screen.getByLabelText("What did you do?"), "Finished a course");
    await user.selectOptions(screen.getByLabelText("About (optional)"), "skill:s1");
    await user.click(screen.getByRole("button", { name: "Add note" }));

    expect(lastCall()).toEqual({
      url: `${BASE}/logs`,
      method: "POST",
      body: { note: "Finished a course", goal_id: null, skill_id: "s1" },
    });
    expect(await screen.findByText("Finished a course")).toBeVisible();
  });

  it("adds and removes your skills", async () => {
    const user = userEvent.setup();
    fetchMock
      .mockResolvedValueOnce(json(201, { ...MY_SKILL, id: "s3", name: "SQL" }))
      .mockResolvedValueOnce(json(204));
    renderSpace();

    await user.type(screen.getByLabelText("A skill you want to grow"), "SQL");
    await user.click(screen.getByRole("button", { name: "Add skill" }));
    expect(await screen.findByText("SQL")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Remove Python" }));
    expect(lastCall()).toEqual({ url: `${BASE}/skills/s1`, method: "DELETE", body: undefined });
    expect(screen.queryByText("Python")).not.toBeInTheDocument();
  });

  it("shows API errors where they happened", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(
      json(409, {
        error: { code: "too_many_goals", message: "x", request_id: null, details: null },
      }),
    );
    renderSpace();
    await user.type(screen.getByLabelText("New goal"), "One more");
    await user.click(screen.getByRole("button", { name: "Add goal" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("most goals allowed");
  });
});
