"use client";

import { useEffect, useRef, type ReactNode } from "react";

import { cx } from "../ui/cx";

const FINE_HOVER = "(hover: hover) and (pointer: fine)";
const REDUCED_MOTION = "(prefers-reduced-motion: reduce)";

/**
 * Hover tilt for the Home cards (ADR 0019): the card under the mouse pops toward you and
 * tilts toward the pointer, then eases back flat. The pointer position goes into CSS custom
 * properties (`--rx`, `--ry`, `--s`, `--lift`, and `--nx`/`--ny` for the depth shift of a
 * `.tilt-shift` child); the transform itself lives in `.tilt` in globals.css.
 *
 * Nothing is attached on touch screens or with reduced motion.
 */
export function Tilt({
  children,
  className,
  maxTilt = 6,
  scale = 1.04,
}: {
  children: ReactNode;
  className?: string;
  /** The most the card rotates, in degrees, at its edge. */
  maxTilt?: number;
  /** How far the card pops forward while hovered. */
  scale?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element || typeof window.matchMedia !== "function") return;
    if (!window.matchMedia(FINE_HOVER).matches || window.matchMedia(REDUCED_MOTION).matches) {
      return;
    }

    let frame = 0;
    let point = { x: 0, y: 0 };

    function apply(nx: number, ny: number) {
      if (!element) return;
      element.style.setProperty("--rx", `${(-ny * maxTilt).toFixed(2)}deg`);
      element.style.setProperty("--ry", `${(nx * maxTilt).toFixed(2)}deg`);
      element.style.setProperty("--nx", nx.toFixed(3));
      element.style.setProperty("--ny", ny.toFixed(3));
    }

    function update() {
      frame = 0;
      if (!element) return;
      const box = element.getBoundingClientRect();
      if (box.width === 0 || box.height === 0) return;
      const nx = ((point.x - box.left) / box.width) * 2 - 1;
      const ny = ((point.y - box.top) / box.height) * 2 - 1;
      apply(Math.max(-1, Math.min(1, nx)), Math.max(-1, Math.min(1, ny)));
    }

    function enter() {
      if (!element) return;
      element.dataset.tilting = "";
      element.style.setProperty("--s", String(scale));
      element.style.setProperty("--lift", "-2px");
    }

    function move(event: PointerEvent) {
      point = { x: event.clientX, y: event.clientY };
      if (!frame) frame = window.requestAnimationFrame(update);
    }

    function leave() {
      if (!element) return;
      if (frame) window.cancelAnimationFrame(frame);
      frame = 0;
      delete element.dataset.tilting;
      apply(0, 0);
      element.style.setProperty("--s", "1");
      element.style.setProperty("--lift", "0px");
    }

    element.addEventListener("pointerenter", enter);
    element.addEventListener("pointermove", move);
    element.addEventListener("pointerleave", leave);
    return () => {
      if (frame) window.cancelAnimationFrame(frame);
      element.removeEventListener("pointerenter", enter);
      element.removeEventListener("pointermove", move);
      element.removeEventListener("pointerleave", leave);
    };
  }, [maxTilt, scale]);

  return (
    <div ref={ref} className={cx("tilt", className)}>
      {children}
    </div>
  );
}
