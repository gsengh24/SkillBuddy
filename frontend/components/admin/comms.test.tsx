import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { NewBanner, RetryEmail } from "./comms";

const router = { replace: vi.fn(), refresh: vi.fn(), push: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router }));

const REASON = "Planned database maintenance tonight";

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

function sent(): { url: string; body: unknown } {
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  return { url, body: JSON.parse(String(init.body)) };
}

describe("NewBanner", () => {
  it("previews the text and publishes it with the type and a reason", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          id: "b1",
          message: "Down on Sunday",
          kind: "warning",
          created_at: "2026-10-09T10:00:00Z",
          ends_at: null,
          ended_at: null,
          live: true,
        }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      ),
    );
    const user = userEvent.setup({ delay: null });
    render(<NewBanner />);
    await user.type(screen.getByLabelText(/Message/), "Down on Sunday");
    await user.click(screen.getByRole("button", { name: "Warning" }));
    expect(screen.getAllByText("Down on Sunday").length).toBeGreaterThan(0);
    await user.click(screen.getByRole("button", { name: "Publish banner" }));
    const dialog = screen.getByRole("dialog", { name: "Publish this banner?" });
    await user.type(within(dialog).getByLabelText(/Reason/), REASON);
    await user.click(within(dialog).getByRole("button", { name: "Publish" }));

    expect(sent()).toEqual({
      url: "/api/v1/admin/comms/banners",
      body: { message: "Down on Sunday", kind: "warning", ends_at: null, reason: REASON },
    });
    expect(router.refresh).toHaveBeenCalled();
  });

  it("can't publish an empty message", () => {
    render(<NewBanner />);
    expect(screen.getByRole("button", { name: "Publish banner" })).toBeDisabled();
  });
});

describe("RetryEmail", () => {
  it("retries a failed email with a reason", async () => {
    const user = userEvent.setup({ delay: null });
    render(
      <RetryEmail
        send={{
          id: "e1",
          created_at: "2026-10-09T10:00:00Z",
          to: "sam@example.com",
          template: "invite",
          status: "failed",
          error: "Timeout",
          retryable: true,
          retried_at: null,
        }}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Retry" }));
    const dialog = screen.getByRole("dialog", { name: "Retry the email to sam@example.com?" });
    await user.type(within(dialog).getByLabelText(/Reason/), REASON);
    await user.click(within(dialog).getByRole("button", { name: "Retry" }));
    expect(sent()).toEqual({
      url: "/api/v1/admin/comms/emails/e1/retry",
      body: { reason: REASON },
    });
  });
});
