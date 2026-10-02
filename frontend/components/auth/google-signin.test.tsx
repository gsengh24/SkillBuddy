import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { messageForCode } from "@/lib/auth/messages";

import { LoginForm } from "./login-form";

const router = { replace: vi.fn(), refresh: vi.fn(), push: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router }));

const GOOGLE_URL = "https://accounts.google.com/o/oauth2/v2/auth?client_id=x&state=y";

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

let fetchMock: ReturnType<typeof vi.fn>;
const assign = vi.fn();
const realLocation = window.location;

beforeEach(() => {
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
  assign.mockReset();
  Object.defineProperty(window, "location", {
    configurable: true,
    value: { ...realLocation, assign },
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  Object.defineProperty(window, "location", { configurable: true, value: realLocation });
});

describe("Continue with Google", () => {
  it("is hidden unless the API offers it", () => {
    render(<LoginForm nextPath="/home" />);
    expect(screen.queryByRole("button", { name: "Continue with Google" })).not.toBeInTheDocument();
  });

  it("comes before the email option and names the allowed domain", () => {
    render(<LoginForm nextPath="/home" google={{ domains: ["thapar.edu"] }} />);
    const google = screen.getByRole("button", { name: "Continue with Google" });
    const email = screen.getByLabelText("Email address");
    expect(google.compareDocumentPosition(email) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByText("Only @thapar.edu Google accounts.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Email me a code" })).toBeInTheDocument();
  });

  it("needs the same tick boxes before leaving for Google", async () => {
    const user = userEvent.setup();
    render(<LoginForm nextPath="/home" google={{ domains: ["thapar.edu"] }} />);
    await user.click(screen.getByRole("button", { name: "Continue with Google" }));
    expect(screen.getByRole("alert")).toHaveTextContent(/18 or older/);
    expect(fetchMock).not.toHaveBeenCalled();
    expect(assign).not.toHaveBeenCalled();
  });

  it("starts the attempt and sends the browser to Google", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValueOnce(json(200, { authorization_url: GOOGLE_URL }));
    render(<LoginForm nextPath="/profile" google={{ domains: ["thapar.edu"] }} />);

    await user.click(screen.getByRole("checkbox", { name: /18 or older/ }));
    await user.click(screen.getByRole("checkbox", { name: /accept the/ }));
    await user.click(screen.getByRole("button", { name: "Continue with Google" }));

    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/auth/google/start");
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      age_confirmed: true,
      accept_terms: true,
      next: "/profile",
    });
    expect(assign).toHaveBeenCalledWith(GOOGLE_URL);
  });

  it("shows the reason when Google sign-in sent the person back", () => {
    render(
      <LoginForm
        nextPath="/home"
        google={{ domains: ["thapar.edu"] }}
        initialError={messageForCode("email_not_allowed")}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("can't be used to sign in here");
  });
});

describe("messageForCode", () => {
  it("knows the Google codes and ignores anything else", () => {
    expect(messageForCode("google_state_invalid")).toMatch(/expired or was already used/);
    expect(messageForCode("consent_required")).toMatch(/18 or older/);
    expect(messageForCode("<script>")).toBeNull();
    expect(messageForCode("toString")).toBeNull();
    expect(messageForCode(undefined)).toBeNull();
  });
});
