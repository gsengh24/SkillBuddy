import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Space } from "@/lib/api/schemas";

import { SpaceView } from "./space-view";

/*
 * Keyboard checks on the restyled pair space (PR 5). Behaviour and wording are covered by
 * spaces.test.tsx, unchanged.
 */

const ME = "me";
const THEM = "them";
const SPACE: Space = {
  connection_id: "c1",
  goals: [
    {
      id: "g1",
      title: "Ship the MVP",
      status: "open",
      due_on: null,
      done_at: null,
      created_by: THEM,
      created_at: "2026-10-04T10:00:00Z",
    },
  ],
  skills: [{ id: "s1", name: "Python", owner_id: ME, created_at: "2026-10-04T10:00:00Z" }],
  logs: [],
  retention_days: 90,
  max_goals: 30,
  max_skills_per_person: 10,
};

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn(async () => new Response(null, { status: 204 }));
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function renderSpace() {
  return render(<SpaceView space={SPACE} meId={ME} otherId={THEM} otherName="Asha" />);
}

describe("pair space, from the keyboard", () => {
  it("names each section by its heading", () => {
    renderSpace();
    for (const name of ["Shared goals", "Skills to grow", "Progress notes"]) {
      expect(screen.getByRole("region", { name })).toBeInTheDocument();
    }
  });

  it("toggles a goal with Space, and reaches its Report and Delete by Tab", async () => {
    renderSpace();
    const user = userEvent.setup();
    const goals = screen.getByRole("region", { name: "Shared goals" });
    const goal = within(goals).getByRole("checkbox", { name: /Ship the MVP/ });
    goal.focus();
    await user.tab();
    expect(within(goals).getByRole("button", { name: "Report" })).toHaveFocus();
    await user.tab();
    expect(within(goals).getByRole("button", { name: "Delete" })).toHaveFocus();
    goal.focus();
    await user.keyboard(" ");
    expect(fetchMock).toHaveBeenCalled();
  });

  it("adds a goal by pressing Enter in its field", async () => {
    renderSpace();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("New goal"), "Launch{Enter}");
    const [url, init] = fetchMock.mock.calls.at(-1) as [string, RequestInit];
    expect(url).toContain("/connections/c1/space/goals");
    expect(init.method).toBe("POST");
  });

  it("labels the skill remove button and the note's About select", () => {
    renderSpace();
    expect(screen.getByRole("button", { name: "Remove Python" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "About (optional)" })).toBeInTheDocument();
    expect(screen.getByLabelText("What did you do?")).toBeInTheDocument();
  });
});
