import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ProcessRequest, StartCsv } from "./data";

const router = { replace: vi.fn(), refresh: vi.fn(), push: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router }));

const REASON = "Asked by email; identity checked";

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

describe("ProcessRequest", () => {
  it("deletes an account now only after a reason", async () => {
    const user = userEvent.setup({ delay: null });
    render(<ProcessRequest kind="deletion" id="u1" email="sam@example.com" />);
    await user.click(screen.getByRole("button", { name: "Process" }));
    const dialog = screen.getByRole("dialog", { name: "Delete sam@example.com now?" });
    expect(within(dialog).getByText(/can't be undone/)).toBeInTheDocument();
    await user.type(within(dialog).getByLabelText(/Reason/), REASON);
    await user.click(within(dialog).getByRole("button", { name: "Delete permanently" }));

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/admin/data/deletions/u1/process");
    expect(JSON.parse(String(init.body))).toEqual({ reason: REASON });
    expect(router.refresh).toHaveBeenCalled();
  });
});

describe("StartCsv", () => {
  it("queues an export in the background", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          id: "x1",
          kind: "users",
          status: "queued",
          created_at: "2026-10-09T10:00:00Z",
          ready_at: null,
          expires_at: null,
          rows: null,
          size_bytes: null,
        }),
        { status: 202, headers: { "Content-Type": "application/json" } },
      ),
    );
    const user = userEvent.setup({ delay: null });
    render(<StartCsv kind="users" label="Export users" />);
    await user.click(screen.getByRole("button", { name: "Export users" }));
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/admin/data/csv/users");
    expect(await screen.findByRole("status")).toHaveTextContent(/Queued/);
  });
});
