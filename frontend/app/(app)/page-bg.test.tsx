import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import BrowseTeamsPage from "./teams/browse/page";
import TeamsPage from "./teams/page";

vi.mock("server-only", () => ({}));
vi.mock("@/lib/auth/with-user", () => ({
  startEarly: <T,>(call: Promise<T>) => call,
  withUser: async () => ({ user: { id: "u1", email: "dev@example.com" } }),
}));
vi.mock("@/lib/features", () => ({
  getFeatures: async () => ({ features: { teams: false } }),
}));
vi.mock("@/lib/teams/server", () => ({
  getListedTeams: vi.fn(),
  getMyTeamRequests: vi.fn(),
  getTeam: vi.fn(),
  getTeamInvites: vi.fn(),
  getTeamSpace: vi.fn(),
  getTeams: vi.fn(),
}));

describe("softer page background marker", () => {
  it("Pair spaces marks itself", async () => {
    const { container } = render(await TeamsPage());
    expect(container.querySelector('[data-page-bg="soft"]')).not.toBeNull();
  });

  it("other pages do not, such as Find a pair space", async () => {
    const { container } = render(await BrowseTeamsPage({ searchParams: Promise.resolve({}) }));
    expect(container.querySelector("[data-page-bg]")).toBeNull();
  });
});
