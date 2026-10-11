import { render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { notifyHomeChanged } from "@/lib/home/changed";

import { LiveRefresh } from "./live-refresh";

const router = vi.hoisted(() => ({ refresh: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => router }));

let visibility: DocumentVisibilityState;

function comeBackToTab() {
  document.dispatchEvent(new Event("visibilitychange"));
}

beforeEach(() => {
  vi.useFakeTimers();
  router.refresh.mockReset();
  visibility = "visible";
  vi.spyOn(document, "visibilityState", "get").mockImplementation(() => visibility);
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("LiveRefresh", () => {
  it("refreshes every minute while the tab is visible", () => {
    render(<LiveRefresh />);
    vi.advanceTimersByTime(59_000);
    expect(router.refresh).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1_000);
    expect(router.refresh).toHaveBeenCalledTimes(1);
  });

  it("refreshes every 20 seconds while a request is being matched", () => {
    render(<LiveRefresh fast />);
    vi.advanceTimersByTime(20_000);
    expect(router.refresh).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(20_000);
    expect(router.refresh).toHaveBeenCalledTimes(2);
  });

  it("does not refresh a hidden tab", () => {
    visibility = "hidden";
    render(<LiveRefresh fast />);
    vi.advanceTimersByTime(120_000);
    expect(router.refresh).not.toHaveBeenCalled();
  });

  it("refreshes when the person comes back after a while", () => {
    render(<LiveRefresh />);
    vi.advanceTimersByTime(40_000);
    comeBackToTab();
    expect(router.refresh).toHaveBeenCalledTimes(1);
  });

  it("does not refresh again on a quick return to a page that just loaded or refreshed", () => {
    render(<LiveRefresh />);
    vi.advanceTimersByTime(10_000);
    comeBackToTab();
    expect(router.refresh).not.toHaveBeenCalled();

    vi.advanceTimersByTime(50_000); // the minute is up: one refresh
    expect(router.refresh).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(5_000);
    comeBackToTab();
    expect(router.refresh).toHaveBeenCalledTimes(1);
  });

  it("refreshes at once when something the inbox shows has changed, even just after a refresh", () => {
    render(<LiveRefresh />);
    notifyHomeChanged();
    expect(router.refresh).toHaveBeenCalledTimes(1);
    notifyHomeChanged();
    expect(router.refresh).toHaveBeenCalledTimes(2);
  });

  it("stops when it is removed", () => {
    const { unmount } = render(<LiveRefresh fast />);
    unmount();
    vi.advanceTimersByTime(120_000);
    comeBackToTab();
    notifyHomeChanged();
    expect(router.refresh).not.toHaveBeenCalled();
  });
});
