import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DataDownload, DeviceList, PauseAccount } from "./account-controls";

const router = { replace: vi.fn(), refresh: vi.fn(), push: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router }));

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const DEVICES = [
  {
    id: "here",
    device: "Chrome on Windows",
    current: true,
    created_at: "2026-10-01T10:00:00Z",
    last_seen_at: "2026-10-08T10:00:00Z",
  },
  {
    id: "phone",
    device: "Safari on iPhone",
    current: false,
    created_at: "2026-10-01T10:00:00Z",
    last_seen_at: "2026-10-06T10:00:00Z",
  },
  {
    id: "tablet",
    device: "Chrome on Android",
    current: false,
    created_at: "2026-10-01T10:00:00Z",
    last_seen_at: "2026-09-28T10:00:00Z",
  },
];

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn(async () => new Response(null, { status: 204 }));
  vi.stubGlobal("fetch", fetchMock);
  router.refresh.mockReset();
  document.cookie = "csrf_token=csrf-value-123; path=/";
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("DeviceList", () => {
  it("marks this device and signs out another one", async () => {
    render(<DeviceList initial={DEVICES} />);
    expect(screen.getByText("This device")).toBeInTheDocument();
    await userEvent
      .setup({ delay: null })
      .click(screen.getByRole("button", { name: /^Sign out Safari on iPhone/ }));

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/auth/sessions/phone");
    expect(init.method).toBe("DELETE");
    expect(screen.queryByText("Safari on iPhone")).not.toBeInTheDocument();
    expect(screen.getByText("Chrome on Android")).toBeInTheDocument();
  });

  it("signs out every other device at once, keeping this one", async () => {
    render(<DeviceList initial={DEVICES} />);
    await userEvent
      .setup({ delay: null })
      .click(screen.getByRole("button", { name: "Sign out of all other devices" }));

    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/auth/logout-others");
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    expect(
      screen.queryByRole("button", { name: "Sign out of all other devices" }),
    ).not.toBeInTheDocument();
  });

  it("says when signing out a device fails", async () => {
    fetchMock.mockResolvedValueOnce(
      json(404, {
        error: { code: "session_not_found", message: "x", request_id: null, details: null },
      }),
    );
    render(<DeviceList initial={DEVICES} />);
    await userEvent
      .setup({ delay: null })
      .click(screen.getByRole("button", { name: /^Sign out Chrome on Android/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("already signed out");
  });
});

describe("DataDownload", () => {
  it("asks for the file and says a link is on its way", async () => {
    fetchMock.mockResolvedValueOnce(
      json(202, {
        id: "e1",
        status: "requested",
        requested_at: "2026-10-08T10:00:00Z",
        ready_at: null,
        expires_at: null,
        downloaded_at: null,
      }),
    );
    render(<DataDownload initial={[]} />);
    await userEvent.setup({ delay: null }).click(screen.getByRole("button", { name: "Request" }));

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/me/data-exports");
    expect(init.method).toBe("POST");
    expect(screen.getByRole("status")).toHaveTextContent(/email you a link/);
    expect(screen.getByRole("button", { name: "Requested" })).toBeDisabled();
  });

  it("explains a recent request", async () => {
    fetchMock.mockResolvedValueOnce(
      json(409, {
        error: { code: "data_export_recent", message: "x", request_id: null, details: null },
      }),
    );
    render(<DataDownload initial={[]} />);
    await userEvent.setup({ delay: null }).click(screen.getByRole("button", { name: "Request" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/asked for your data recently/);
  });

  it("shows a failed request so it can be asked again", () => {
    render(
      <DataDownload
        initial={[
          {
            id: "e1",
            status: "failed",
            requested_at: "2026-10-08T10:00:00Z",
            ready_at: null,
            expires_at: null,
            downloaded_at: null,
          },
        ]}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent(/ask again/);
    expect(screen.getByRole("button", { name: "Request" })).toBeEnabled();
  });
});

describe("PauseAccount", () => {
  const user = {
    id: "u1",
    email: "a@example.com",
    created_at: "2026-10-01T10:00:00Z",
    email_verified_at: null,
    last_login_at: null,
    terms_version: null,
    terms_accepted_at: null,
  };

  it("pauses, then resumes", async () => {
    fetchMock
      .mockResolvedValueOnce(json(200, { ...user, status: "paused" }))
      .mockResolvedValueOnce(json(200, { ...user, status: "active" }));
    const actions = userEvent.setup({ delay: null });
    render(<PauseAccount initial="active" />);

    await actions.click(screen.getByRole("button", { name: "Pause" }));
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/me/pause");
    expect(screen.getByText("Your account is paused")).toBeInTheDocument();

    await actions.click(screen.getByRole("button", { name: "Resume" }));
    expect(fetchMock.mock.calls[1]?.[0]).toBe("/api/v1/me/resume");
    expect(screen.getByText("Pause my account")).toBeInTheDocument();
    expect(router.refresh).toHaveBeenCalledTimes(2);
  });
});
