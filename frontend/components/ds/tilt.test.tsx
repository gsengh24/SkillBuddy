import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Tilt } from "./tilt";

function screenIs({ fine, reduced }: { fine: boolean; reduced: boolean }) {
  window.matchMedia = vi.fn((query: string) => ({
    matches: query.includes("reduced-motion") ? reduced : fine,
  })) as never;
}

function setup() {
  render(<Tilt>card</Tilt>);
  const card = screen.getByText("card");
  vi.spyOn(card, "getBoundingClientRect").mockReturnValue({
    left: 0,
    top: 0,
    width: 200,
    height: 100,
    right: 200,
    bottom: 100,
    x: 0,
    y: 0,
    toJSON: () => ({}),
  });
  return card;
}

const deg = (card: HTMLElement, name: string) => parseFloat(card.style.getPropertyValue(name));

describe("Tilt", () => {
  beforeEach(() => {
    vi.spyOn(window, "requestAnimationFrame").mockImplementation((callback) => {
      callback(0);
      return 1;
    });
  });
  afterEach(() => vi.restoreAllMocks());

  it("attaches nothing with reduced motion", () => {
    screenIs({ fine: true, reduced: true });
    const card = setup();
    fireEvent.pointerEnter(card);
    fireEvent.pointerMove(card, { clientX: 200, clientY: 0 });
    expect(card.getAttribute("style")).toBeNull();
    expect(card).not.toHaveAttribute("data-tilting");
  });

  it("attaches nothing with a coarse pointer", () => {
    screenIs({ fine: false, reduced: false });
    const card = setup();
    fireEvent.pointerEnter(card);
    fireEvent.pointerMove(card, { clientX: 200, clientY: 0 });
    expect(card.getAttribute("style")).toBeNull();
  });

  it("pops forward on enter and tilts within 6 degrees, away at the top right", () => {
    screenIs({ fine: true, reduced: false });
    const card = setup();
    fireEvent.pointerEnter(card);
    expect(card.style.getPropertyValue("--s")).toBe("1.04");
    expect(card.style.getPropertyValue("--lift")).toBe("-2px");
    fireEvent.pointerMove(card, { clientX: 200, clientY: 0 });
    expect(deg(card, "--rx")).toBeCloseTo(6);
    expect(deg(card, "--ry")).toBeCloseTo(6);
    // Far outside the card still clamps.
    fireEvent.pointerMove(card, { clientX: 5000, clientY: -5000 });
    expect(Math.abs(deg(card, "--rx"))).toBeLessThanOrEqual(6);
    expect(Math.abs(deg(card, "--ry"))).toBeLessThanOrEqual(6);
  });

  it("stays flat with the pointer at the centre", () => {
    screenIs({ fine: true, reduced: false });
    const card = setup();
    fireEvent.pointerEnter(card);
    fireEvent.pointerMove(card, { clientX: 100, clientY: 50 });
    expect(Math.abs(deg(card, "--rx"))).toBeCloseTo(0);
    expect(Math.abs(deg(card, "--ry"))).toBeCloseTo(0);
  });

  it("resets to flat on pointer leave", () => {
    screenIs({ fine: true, reduced: false });
    const card = setup();
    fireEvent.pointerEnter(card);
    fireEvent.pointerMove(card, { clientX: 200, clientY: 0 });
    fireEvent.pointerLeave(card);
    expect(Math.abs(deg(card, "--rx"))).toBe(0);
    expect(Math.abs(deg(card, "--ry"))).toBe(0);
    expect(card.style.getPropertyValue("--s")).toBe("1");
    expect(card).not.toHaveAttribute("data-tilting");
  });
});
