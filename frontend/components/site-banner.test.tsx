import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SiteBanner } from "./site-banner";

let pathname = "/home";
vi.mock("next/navigation", () => ({ usePathname: () => pathname }));

const BANNER = {
  id: "b1",
  announcement: "<b>Down</b> on Sunday 2:00 AM",
  kind: "maintenance",
  ends_at: null,
};

let fetchMock: ReturnType<typeof vi.fn>;

function respond(banner: unknown) {
  fetchMock.mockImplementation(
    async () =>
      new Response(JSON.stringify({ banner }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
  );
}

beforeEach(() => {
  pathname = "/home";
  window.localStorage.clear();
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("SiteBanner", () => {
  it("shows the active banner as plain text", async () => {
    respond(BANNER);
    render(<SiteBanner />);
    expect(await screen.findByText("<b>Down</b> on Sunday 2:00 AM")).toBeInTheDocument();
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/banner");
  });

  it("stays hidden after it is dismissed", async () => {
    respond(BANNER);
    const user = userEvent.setup();
    const { unmount } = render(<SiteBanner />);
    await user.click(await screen.findByRole("button", { name: "Dismiss announcement" }));
    expect(screen.queryByText(/Down/)).not.toBeInTheDocument();
    unmount();

    render(<SiteBanner />);
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(screen.queryByText(/Down/)).not.toBeInTheDocument();
  });

  it("shows nothing when there is no banner", async () => {
    respond(null);
    render(<SiteBanner />);
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("is not shown in the admin portal", () => {
    pathname = "/admin/comms";
    respond(BANNER);
    render(<SiteBanner />);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
