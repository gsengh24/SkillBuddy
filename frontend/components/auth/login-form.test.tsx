import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LoginForm } from "./login-form";

const router = { replace: vi.fn(), refresh: vi.fn(), push: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router }));

const USER = {
  id: "8d3f4b2a-0000-4000-8000-000000000001",
  email: "ananya@example.com",
  created_at: "2026-10-01T10:00:00Z",
  email_verified_at: "2026-10-01T10:00:00Z",
  last_login_at: "2026-10-01T10:00:00Z",
  terms_version: "2026-10-01-draft",
  terms_accepted_at: "2026-10-01T10:00:00Z",
};
const SENT = { status: "sent", message: "On its way.", expires_in_seconds: 600 };

function json(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

function apiError(status: number, code: string, message = "Server message.") {
  return json(status, { error: { code, message, request_id: "r1", details: null } });
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  router.replace.mockReset();
  router.refresh.mockReset();
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

async function fillFirstStep(user: ReturnType<typeof userEvent.setup>, consent = true) {
  await user.type(screen.getByLabelText("Email address"), "ananya@example.com");
  if (consent) {
    await user.click(screen.getByRole("checkbox", { name: /18 or older/ }));
    await user.click(screen.getByRole("checkbox", { name: /accept the/ }));
  }
  await user.click(screen.getByRole("button", { name: "Email me a code" }));
}

describe("LoginForm", () => {
  it("requires age confirmation and the terms before sending a code", async () => {
    const user = userEvent.setup();
    render(<LoginForm nextPath="/home" />);

    await fillFirstStep(user, false);

    expect(screen.getByRole("alert")).toHaveTextContent(/18 or older and accept the terms/);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("requires the 18+ box even when the terms are accepted", async () => {
    const user = userEvent.setup();
    render(<LoginForm nextPath="/home" />);

    await user.type(screen.getByLabelText("Email address"), "ananya@example.com");
    await user.click(screen.getByRole("checkbox", { name: /accept the/ }));
    await user.click(screen.getByRole("button", { name: "Email me a code" }));

    expect(screen.getByRole("alert")).toHaveTextContent(/18 or older and accept the terms/);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects an invalid email address without calling the API", async () => {
    const user = userEvent.setup();
    render(<LoginForm nextPath="/home" />);

    await user.type(screen.getByLabelText("Email address"), "not-an-email");
    await user.click(screen.getByRole("button", { name: "Email me a code" }));

    expect(screen.getByRole("alert")).toHaveTextContent(/valid email address/);
    expect(screen.getByLabelText("Email address")).toHaveAttribute("aria-invalid", "true");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("sends the code and moves focus to the code field with a resend countdown", async () => {
    fetchMock.mockResolvedValueOnce(json(202, SENT));
    const user = userEvent.setup();
    render(<LoginForm nextPath="/home" />);

    await fillFirstStep(user);

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/auth/otp/request",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ email: "ananya@example.com" }),
      }),
    );
    expect(await screen.findByRole("heading", { name: "Check your email" })).toBeInTheDocument();
    expect(screen.getByLabelText("Sign-in code")).toHaveFocus();
    expect(screen.getByRole("button", { name: /Resend code in 60s/ })).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent(/sent a 6-digit code/);
  });

  it("enables resending once the countdown ends", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    // A fresh Response per call: a body can only be read once.
    fetchMock.mockImplementation(() => Promise.resolve(json(202, SENT)));
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<LoginForm nextPath="/home" />);
    await fillFirstStep(user);
    await screen.findByRole("heading", { name: "Check your email" });

    act(() => {
      vi.advanceTimersByTime(61_000);
    });
    const resend = screen.getByRole("button", { name: "Resend code" });
    expect(resend).toBeEnabled();

    await user.click(resend);
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(await screen.findByRole("button", { name: /Resend code in/ })).toBeDisabled();
  });

  it("shows a clear message for a wrong code and keeps the focus on the field", async () => {
    fetchMock
      .mockResolvedValueOnce(json(202, SENT))
      .mockResolvedValueOnce(apiError(400, "invalid_code"));
    const user = userEvent.setup();
    render(<LoginForm nextPath="/home" />);
    await fillFirstStep(user);

    await user.type(await screen.findByLabelText("Sign-in code"), "123456");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/incorrect or has expired/);
    expect(screen.getByLabelText("Sign-in code")).toHaveFocus();
    expect(router.replace).not.toHaveBeenCalled();
  });

  it("explains rate limits with the time to wait", async () => {
    fetchMock.mockResolvedValueOnce(
      json(
        429,
        { error: { code: "rate_limited", message: "x", request_id: null, details: null } },
        { "Retry-After": "120" },
      ),
    );
    const user = userEvent.setup();
    render(<LoginForm nextPath="/home" />);

    await fillFirstStep(user);

    expect(await screen.findByRole("alert")).toHaveTextContent(/wait about 2 minutes/);
    expect(screen.getByRole("heading", { name: /Sign in to/ })).toBeInTheDocument();
  });

  it("shows the server's message when the account is pending deletion", async () => {
    fetchMock
      .mockResolvedValueOnce(json(202, SENT))
      .mockResolvedValueOnce(
        apiError(403, "account_pending_deletion", "Scheduled for deletion on 2026-10-31."),
      );
    const user = userEvent.setup();
    render(<LoginForm nextPath="/home" />);
    await fillFirstStep(user);

    await user.type(await screen.findByLabelText("Sign-in code"), "123456");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Scheduled for deletion on 2026-10-31.",
    );
  });

  it("signs in with consent flags and goes to the next page", async () => {
    fetchMock.mockResolvedValueOnce(json(202, SENT)).mockResolvedValueOnce(json(200, USER));
    const user = userEvent.setup();
    render(<LoginForm nextPath="/settings/account" />);
    await fillFirstStep(user);

    await user.type(await screen.findByLabelText("Sign-in code"), "12a34 56");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    const [, init] = fetchMock.mock.calls[1] as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({
      email: "ananya@example.com",
      code: "123456",
      age_confirmed: true,
      accept_terms: true,
    });
    expect(router.replace).toHaveBeenCalledWith("/settings/account");
  });

  it("lets the user go back and change the email", async () => {
    fetchMock.mockResolvedValueOnce(json(202, SENT));
    const user = userEvent.setup();
    render(<LoginForm nextPath="/home" />);
    await fillFirstStep(user);

    await user.click(await screen.findByRole("button", { name: "Use a different email" }));

    expect(screen.getByLabelText("Email address")).toHaveValue("ananya@example.com");
    expect(screen.getByLabelText("Email address")).toHaveFocus();
  });

  it("reports network failures in plain language", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    const user = userEvent.setup();
    render(<LoginForm nextPath="/home" />);

    await fillFirstStep(user);

    expect(await screen.findByRole("alert")).toHaveTextContent(/couldn't reach the server/);
  });

  it("has no invite code field unless signups are invite only", () => {
    render(<LoginForm nextPath="/home" />);
    expect(screen.queryByLabelText(/Invite code/)).not.toBeInTheDocument();
  });

  it("sends the invite code with the sign-in when signups are invite only", async () => {
    fetchMock.mockResolvedValueOnce(json(202, SENT)).mockResolvedValueOnce(json(200, USER));
    const user = userEvent.setup();
    render(<LoginForm nextPath="/home" inviteOnly />);
    await user.type(screen.getByLabelText(/Invite code/), " cyn-friends ");
    await fillFirstStep(user);

    await user.type(await screen.findByLabelText("Sign-in code"), "123456");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    const [, init] = fetchMock.mock.calls[1] as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({
      email: "ananya@example.com",
      code: "123456",
      age_confirmed: true,
      accept_terms: true,
      invite_code: "cyn-friends",
    });
  });

  it("explains when an invite is needed", async () => {
    fetchMock
      .mockResolvedValueOnce(json(202, SENT))
      .mockResolvedValueOnce(apiError(403, "invite_required"));
    const user = userEvent.setup();
    render(<LoginForm nextPath="/home" inviteOnly />);
    await fillFirstStep(user);

    await user.type(await screen.findByLabelText("Sign-in code"), "123456");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/Enter an invite code/);
  });
});
