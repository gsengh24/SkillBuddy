import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ScreensPage, { metadata } from "./page";

const NOT_FOUND = new Error("NEXT_NOT_FOUND");
vi.mock("next/navigation", () => ({
  notFound: () => {
    throw NOT_FOUND;
  },
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}));
vi.mock("server-only", () => ({}));
vi.mock("@/lib/api/browser", () => ({ browserApi: vi.fn(() => new Promise(() => undefined)) }));

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("/design/screens", () => {
  it("is a 404 when the style-guide flag is off", () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("VERCEL_ENV", "production");
    expect(() => ScreensPage()).toThrow(NOT_FOUND);
  });

  it("shows the match, intro and chat screens on previews, and is not indexed", () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("VERCEL_ENV", "preview");
    render(<ScreensPage />);
    for (const name of ["Match cards", "An intro you received", "A chat"]) {
      expect(screen.getByRole("heading", { level: 2, name })).toBeInTheDocument();
    }
    expect(metadata.robots).toEqual({ index: false, follow: false });
  });
});
