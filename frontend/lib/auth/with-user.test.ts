import { beforeEach, describe, expect, it, vi } from "vitest";

import type { User } from "@/lib/api/schemas";

import { getCurrentUser } from "./session";
import { startEarly, withUser } from "./with-user";

vi.mock("server-only", () => ({}));
vi.mock("./session", () => ({ getCurrentUser: vi.fn() }));
const REDIRECT = new Error("NEXT_REDIRECT");
vi.mock("next/navigation", () => ({
  redirect: vi.fn(() => {
    throw REDIRECT;
  }),
}));

const USER = { id: "11111111-0000-4000-8000-000000000001", email: "a@example.com" } as User;

/** A promise the test settles by hand, to see what runs before what. */
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe("withUser", () => {
  beforeEach(() => {
    vi.mocked(getCurrentUser).mockReset();
  });

  it("runs the session check and the data call at the same time", async () => {
    const session = deferred<User | null>();
    const data = deferred<string>();
    vi.mocked(getCurrentUser).mockReturnValue(session.promise);

    const result = withUser("/login?next=/x", data.promise);
    // Both are in flight: settle the data first, then the session.
    data.resolve("connections");
    session.resolve(USER);

    await expect(result).resolves.toEqual({ user: USER, data: "connections" });
    expect(getCurrentUser).toHaveBeenCalledOnce();
  });

  it("sends signed-out visitors to the login page and ignores the data call's 401", async () => {
    vi.mocked(getCurrentUser).mockResolvedValue(null);
    const data = Promise.reject(new Error("401"));

    await expect(withUser("/login?next=/messages", data)).rejects.toBe(REDIRECT);
    const { redirect } = await import("next/navigation");
    expect(redirect).toHaveBeenCalledWith("/login?next=/messages");
  });

  it("throws the data call's failure for a signed-in user", async () => {
    vi.mocked(getCurrentUser).mockResolvedValue(USER);
    const failure = new Error("503");

    await expect(withUser("/login", Promise.reject(failure))).rejects.toBe(failure);
  });
});

describe("startEarly", () => {
  it("returns the same result, and a failure nobody awaits is not unhandled", async () => {
    await expect(startEarly(Promise.resolve(3))).resolves.toBe(3);
    const failure = new Error("404");
    const call = startEarly(Promise.reject(failure));
    await new Promise((resolve) => setTimeout(resolve, 0));
    await expect(call).rejects.toBe(failure);
  });
});
