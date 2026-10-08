import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Flag } from "@/lib/admin/schemas";

import { FlagActions, ProviderSwitch, RerunForm, RuleSwitch } from "./content";

const router = { replace: vi.fn(), refresh: vi.fn(), push: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router }));

const REASON = "Checked against the community rules";
const FLAG: Flag = {
  id: "f1",
  rule: "contact_details",
  item_type: "profile",
  item_id: "u1",
  user_id: "u1",
  email: "sam@example.com",
  flagged_text: "Call me on 98765 43210",
  created_at: "2026-10-01T10:00:00Z",
};

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

async function giveReason(
  user: ReturnType<typeof userEvent.setup>,
  dialog: string,
  confirm: string,
) {
  const box = screen.getByRole("dialog", { name: dialog });
  await user.type(within(box).getByLabelText(/Reason/), REASON);
  await user.click(within(box).getByRole("button", { name: confirm }));
}

describe("FlagActions", () => {
  it("removes the text after a reason", async () => {
    const user = userEvent.setup({ delay: null });
    render(<FlagActions flag={FLAG} />);
    await user.click(screen.getByRole("button", { name: "Remove" }));
    await giveReason(user, "Remove this text?", "Remove");
    expect(sent()).toEqual({
      url: "/api/v1/admin/content/flags/f1/decide",
      body: { decision: "remove", reason: REASON },
    });
    expect(router.refresh).toHaveBeenCalled();
  });
});

describe("RuleSwitch", () => {
  it("is read only without the settings permission", () => {
    render(<RuleSwitch rule="profanity" on canChange={false} />);
    expect(screen.getByRole("switch", { name: /Profanity list/ })).toBeDisabled();
  });

  it("turns a rule on with a reason", async () => {
    const user = userEvent.setup({ delay: null });
    render(<RuleSwitch rule="prompt_injection" on={false} canChange />);
    await user.click(screen.getByRole("switch", { name: /Prompt injection/ }));
    await giveReason(user, "Turn on Prompt injection?", "Turn on");
    expect(sent()).toEqual({
      url: "/api/v1/admin/content/rules/prompt_injection",
      body: { on: true, reason: REASON },
    });
  });
});

describe("ProviderSwitch", () => {
  it("sends the provider name in the body", async () => {
    const user = userEvent.setup({ delay: null });
    render(<ProviderSwitch name="cloudflare:@cf/meta/llama" role="fallback" on />);
    await user.click(screen.getByRole("switch", { name: /cloudflare/ }));
    await giveReason(user, "Turn off cloudflare:@cf/meta/llama?", "Turn off");
    expect(sent()).toEqual({
      url: "/api/v1/admin/ai/providers",
      body: { provider: "cloudflare:@cf/meta/llama", on: false, reason: REASON },
    });
  });
});

describe("RerunForm", () => {
  it("queues a re-run by email with a reason", async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ request_id: "r1", status: "queued" }), {
        status: 202,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const user = userEvent.setup({ delay: null });
    render(<RerunForm />);
    await user.type(screen.getByLabelText("Email"), "sam@example.com");
    await user.click(screen.getByRole("button", { name: "Re-run" }));
    await giveReason(user, "Re-run matching for sam@example.com?", "Re-run");
    expect(sent()).toEqual({
      url: "/api/v1/admin/ai/rerun",
      body: { email: "sam@example.com", reason: REASON },
    });
    expect(await screen.findByRole("status")).toHaveTextContent(/Queued/);
  });
});
