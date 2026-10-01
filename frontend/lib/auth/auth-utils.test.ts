import { describe, expect, it } from "vitest";

import { ApiError } from "@/lib/api/errors";

import { describeError } from "./messages";
import { safeNextPath } from "./redirect";

describe("safeNextPath", () => {
  it.each([
    ["/settings/account", "/settings/account"],
    ["/home?tab=1", "/home?tab=1"],
    [undefined, "/home"],
    ["", "/home"],
    ["https://evil.example", "/home"],
    ["//evil.example", "/home"],
    ["/\\evil.example", "/home"],
    ["/login?next=/home", "/home"],
    ["/api/v1/me", "/home"],
  ])("maps %s to %s", (input, expected) => {
    expect(safeNextPath(input)).toBe(expected);
  });
});

describe("describeError", () => {
  const error = (code: string, retryAfter?: number) =>
    new ApiError(
      400,
      { error: { code, message: "from server", request_id: null, details: null } },
      undefined,
      retryAfter,
    );

  it("maps known codes to plain language", () => {
    expect(describeError(error("code_locked"))).toMatch(/Request a new code/);
    expect(describeError(error("signups_paused"))).toMatch(/try again later/);
  });

  it("rounds rate-limit waits up to minutes", () => {
    expect(describeError(error("rate_limited", 30))).toMatch(/about 1 minute\b/);
    expect(describeError(error("rate_limited"))).toMatch(/a few minutes/);
  });

  it("falls back to a generic message for unknown codes and network errors", () => {
    expect(describeError(error("something_new"))).toBe("Something went wrong. Please try again.");
    expect(describeError(new TypeError("Failed to fetch"))).toMatch(/couldn't reach the server/);
  });
});
