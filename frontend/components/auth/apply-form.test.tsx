import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApplyForm } from "./apply-form";

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("ApplyForm", () => {
  it("asks how they heard before sending", async () => {
    const user = userEvent.setup({ delay: null });
    render(<ApplyForm />);
    await user.type(screen.getByLabelText("Email address"), "dev@example.com");
    await user.click(screen.getByRole("button", { name: "Apply to join" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Choose how you heard about us.");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("sends the email and source, then thanks them", async () => {
    fetchMock.mockResolvedValueOnce(json(202, { status: "received" }));
    const user = userEvent.setup({ delay: null });
    render(<ApplyForm />);
    await user.type(screen.getByLabelText("Email address"), "dev@example.com");
    await user.selectOptions(screen.getByLabelText("How did you hear about us?"), "college");
    await user.click(screen.getByRole("button", { name: "Apply to join" }));

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/auth/applications");
    expect(JSON.parse(String(init.body))).toEqual({
      email: "dev@example.com",
      source: "college",
    });
    expect(await screen.findByRole("status")).toHaveTextContent(/email you an invite/);
  });

  it("explains when applications are closed", async () => {
    fetchMock.mockResolvedValueOnce(
      json(409, {
        error: { code: "applications_closed", message: "x", request_id: "r", details: null },
      }),
    );
    const user = userEvent.setup({ delay: null });
    render(<ApplyForm />);
    await user.type(screen.getByLabelText("Email address"), "dev@example.com");
    await user.selectOptions(screen.getByLabelText("How did you hear about us?"), "friend");
    await user.click(screen.getByRole("button", { name: "Apply to join" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /only open while joining is by invite/,
    );
  });
});
