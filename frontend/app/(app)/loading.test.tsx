import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import RootLoading from "../loading";
import AppLoading from "./loading";
import ChatLoading from "./messages/[connectionId]/loading";

describe("loading skeletons", () => {
  it.each([
    ["signed-in pages", AppLoading, "Loading"],
    ["a chat", ChatLoading, "Loading the chat"],
    ["public pages", RootLoading, "Loading"],
  ])("%s announce loading once and hide the blocks", (_name, Loading, label) => {
    const { container } = render(<Loading />);
    expect(screen.getByRole("status")).toHaveTextContent(label);
    const blocks = container.querySelectorAll(".animate-pulse-soft");
    expect(blocks.length).toBeGreaterThan(2);
    for (const block of blocks) expect(block).toHaveAttribute("aria-hidden", "true");
  });
});
