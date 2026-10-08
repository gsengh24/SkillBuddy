import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Health, Overview } from "@/lib/admin/schemas";

import { Attention, Funnel, HealthList, Kpis, SignupChart } from "./overview";

const OVERVIEW: Overview = {
  days: 7,
  generated_at: "2026-10-08T10:00:00Z",
  kpis: [
    { key: "new_signups", value: 12, previous: 8 },
    { key: "intro_accept_rate", value: 50, previous: 60 },
    { key: "messages_sent", value: 3, previous: 0 },
  ],
  signups_by_day: [
    { day: "2026-10-07", count: 4 },
    { day: "2026-10-08", count: 8 },
  ],
  funnel: [
    { step: "requests", count: 10 },
    { step: "intros_accepted", count: 2 },
  ],
  attention: { open_reports: 3, pending_applications: 0 },
  activity: [],
};

describe("Overview pieces", () => {
  it("shows each figure with its change on the previous period", () => {
    render(<Kpis overview={OVERVIEW} />);
    const list = screen.getByRole("list", { name: "Key figures" });
    expect(within(list).getByText("+50% vs previous 7 days")).toBeInTheDocument();
    expect(within(list).getByText("50%")).toBeInTheDocument();
    expect(within(list).getByText("-10 pts vs previous 7 days")).toBeInTheDocument();
    expect(within(list).getByText("new vs previous 7 days")).toBeInTheDocument();
  });

  it("describes the chart for screen readers", () => {
    render(<SignupChart overview={OVERVIEW} />);
    expect(
      screen.getByRole("img", {
        name: "Sign-ups per day: 12 in the last 7 days, at most 8 in a day.",
      }),
    ).toBeInTheDocument();
  });

  it("links each attention row to its page, with 0 for what isn't there", () => {
    render(<Attention overview={OVERVIEW} />);
    expect(screen.getByRole("link", { name: "Open reports: 3" })).toHaveAttribute(
      "href",
      "/admin/reports",
    );
    expect(screen.getByRole("link", { name: "Data requests waiting: 0" })).toHaveAttribute(
      "href",
      "/admin/data",
    );
  });

  it("lists the funnel and the health checks", () => {
    const health: Health = {
      checks: [{ name: "database", status: "ok", detail: "3 ms" }],
      checked_at: "2026-10-08T10:00:00Z",
    };
    render(
      <>
        <Funnel overview={OVERVIEW} />
        <HealthList health={health} />
      </>,
    );
    expect(screen.getByRole("list", { name: "From request to chat" })).toHaveTextContent(
      "Intros accepted",
    );
    expect(screen.getByText("3 ms")).toBeInTheDocument();
  });
});
