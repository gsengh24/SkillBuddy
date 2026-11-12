import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DetailPane } from "./home-panes";

const navigation = vi.hoisted(() => ({ search: "" }));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(navigation.search),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
  usePathname: () => "/home",
}));

beforeEach(() => {
  navigation.search = "";
});

describe("DetailPane", () => {
  it("with nothing open shows the composer and still renders the page (for its redirect)", () => {
    render(
      <DetailPane composer={<p>Composer</p>}>
        <p>Page output</p>
      </DetailPane>,
    );
    expect(screen.getByText("Composer")).toBeVisible();
    // The page normally renders nothing here; a redirect it raises needs it rendered (P7).
    expect(screen.getByText("Page output")).toBeInTheDocument();
  });

  it("with an item open shows the page instead of the composer", () => {
    navigation.search = "item=intro-abc";
    render(
      <DetailPane composer={<p>Composer</p>}>
        <p>Opened intro</p>
      </DetailPane>,
    );
    expect(screen.getByText("Opened intro")).toBeVisible();
    expect(screen.queryByText("Composer")).toBeNull();
  });
});
