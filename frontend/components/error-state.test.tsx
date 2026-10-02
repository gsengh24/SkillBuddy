import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import SignedInError from "@/app/(app)/error";
import RootError from "@/app/error";

import { ErrorState } from "./error-state";

describe("ErrorState", () => {
  it("shows a friendly message and retries on click", async () => {
    const onRetry = vi.fn();
    render(<ErrorState onRetry={onRetry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Something went wrong");
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("shows the error reference when there is one", () => {
    render(<ErrorState digest="abc123" onRetry={() => {}} />);
    expect(screen.getByText("Reference: abc123")).toBeInTheDocument();
  });
});

describe("error boundaries", () => {
  const error = Object.assign(new Error("An unexpected error occurred."), { digest: "d1" });

  it.each([
    ["signed-in pages", SignedInError],
    ["root", RootError],
  ])("%s: render the friendly state and wire retry", async (_, Boundary) => {
    const retry = vi.fn();
    render(<Boundary error={error} retry={retry} />);
    expect(screen.queryByText("An unexpected error occurred.")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalledOnce();
  });
});
