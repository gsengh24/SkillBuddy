import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { COLOUR_PAIRS } from "@/lib/design/pairs";

import DesignPage from "./page";

const NOT_FOUND = new Error("NEXT_NOT_FOUND");
vi.mock("next/navigation", () => ({
  notFound: () => {
    throw NOT_FOUND;
  },
}));

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("/design", () => {
  it("is a 404 in production builds", () => {
    vi.stubEnv("NODE_ENV", "production");
    expect(() => DesignPage()).toThrow(NOT_FOUND);
  });

  it("shows every component section and colour pair in development", () => {
    vi.stubEnv("NODE_ENV", "development");
    render(<DesignPage />);

    expect(screen.getByRole("heading", { level: 1, name: "Design system" })).toBeInTheDocument();
    for (const section of [
      "Neutrals",
      "Hues",
      "Colour pairs and contrast",
      "Typography",
      "Intents",
      "Buttons and links",
      "Avatar, strength bar, match numeral, why-box, tags",
      "Card and hero panel",
      "Text fields",
      "Badges, logo and icons",
    ]) {
      expect(screen.getByRole("heading", { level: 2, name: section })).toBeInTheDocument();
    }
    const table = screen.getByRole("table");
    expect(table.querySelectorAll("tbody tr")).toHaveLength(COLOUR_PAIRS.length);
  });
});
