"use client";

import { useEffect, useRef, useState, type ElementType, type ReactNode } from "react";

import { cx } from "../ui/cx";

/**
 * "static": shown as rendered (on the server, with reduced motion, without
 * IntersectionObserver, or when it was already on screen at load). "hidden": below the
 * fold, waiting. "shown": scrolled into view and faded up. Never re-triggers.
 */
export type InViewState = "static" | "hidden" | "shown";

function prefersReducedMotion(): boolean {
  return (
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

/**
 * The one shared in-view hook (IntersectionObserver). Content is visible in the server
 * HTML; only what starts below the fold is hidden after load and faded up once when it
 * scrolls in, so nothing flashes and nothing is lost without JavaScript.
 */
export function useInView<T extends Element>() {
  const ref = useRef<T>(null);
  const [state, setState] = useState<InViewState>("static");

  useEffect(() => {
    const element = ref.current;
    if (!element || typeof IntersectionObserver === "undefined" || prefersReducedMotion()) {
      return;
    }
    let first = true;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (first) {
            first = false;
            if (entry.isIntersecting) {
              observer.disconnect();
              return;
            }
            setState("hidden");
          } else if (entry.isIntersecting) {
            setState("shown");
            observer.disconnect();
          }
        }
      },
      { threshold: 0.12 },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return { ref, state };
}

const MOTION_CLASSES: Record<InViewState, string> = {
  static: "",
  hidden: "translate-y-2 opacity-0",
  shown: "translate-y-0 opacity-100 transition-[opacity,translate] duration-[450ms] ease-out",
};

/** A section that fades up once (opacity and 8px, 450ms) when it scrolls into view. */
export function FadeUp({
  as: Tag = "div",
  className,
  children,
  ...props
}: {
  as?: ElementType;
  className?: string;
  children: ReactNode;
  id?: string;
  "aria-labelledby"?: string;
}) {
  const { ref, state } = useInView<HTMLElement>();
  return (
    <Tag ref={ref} data-motion={state} className={cx(MOTION_CLASSES[state], className)} {...props}>
      {children}
    </Tag>
  );
}
