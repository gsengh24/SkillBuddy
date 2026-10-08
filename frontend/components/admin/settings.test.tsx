import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FeatureSwitch, LimitField } from "./settings";

const router = { replace: vi.fn(), refresh: vi.fn(), push: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router }));

const REASON = "Incident on the chat service tonight";
const LIMIT = { key: "message_max_length", value: 2000, default: 2000, minimum: 50, maximum: 2000 };

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

describe("FeatureSwitch", () => {
  it("shows the state and turns the feature off only after a reason", async () => {
    const user = userEvent.setup({ delay: null });
    render(<FeatureSwitch feature="chats" on />);
    const toggle = screen.getByRole("switch", { name: /Chats/ });
    expect(toggle).toBeChecked();

    await user.click(toggle);
    const dialog = screen.getByRole("dialog", { name: "Turn off Chats?" });
    const confirm = within(dialog).getByRole("button", { name: "Turn off" });
    expect(confirm).toBeDisabled();
    await user.type(within(dialog).getByLabelText(/Reason/), REASON);
    await user.click(confirm);

    expect(sent()).toEqual({
      url: "/api/v1/admin/settings/features/chats",
      body: { on: false, reason: REASON },
    });
    expect(router.refresh).toHaveBeenCalled();
  });
});

describe("LimitField", () => {
  it("keeps Save off outside the allowed range", async () => {
    const user = userEvent.setup({ delay: null });
    render(<LimitField limit={LIMIT} />);
    const field = screen.getByLabelText("Max message length");
    const save = screen.getByRole("button", { name: "Save" });
    expect(save).toBeDisabled();
    await user.clear(field);
    await user.type(field, "20");
    expect(save).toBeDisabled();
    await user.clear(field);
    await user.type(field, "2001");
    expect(save).toBeDisabled();
  });

  it("saves a new value with a reason", async () => {
    const user = userEvent.setup({ delay: null });
    render(<LimitField limit={LIMIT} />);
    const field = screen.getByLabelText("Max message length");
    await user.clear(field);
    await user.type(field, "500");
    await user.click(screen.getByRole("button", { name: "Save" }));
    const dialog = screen.getByRole("dialog", { name: "Set max message length to 500?" });
    await user.type(within(dialog).getByLabelText(/Reason/), REASON);
    await user.click(within(dialog).getByRole("button", { name: "Save limit" }));

    expect(sent()).toEqual({
      url: "/api/v1/admin/settings/limits/message_max_length",
      body: { value: 500, reason: REASON },
    });
  });
});
