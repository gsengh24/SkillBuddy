"use client";

import { useEffect, useId, useRef, useState, type ReactNode } from "react";

import { cx } from "../ui/cx";

/**
 * A "⋯" button that opens a small panel of actions (for example Block and Report in a chat
 * header, where four buttons don't fit on a phone). It is a disclosure: the button says
 * whether the panel is open (aria-expanded) and which panel it controls, and the actions
 * inside are ordinary buttons with their own flows. Escape closes it and puts focus back on
 * the button.
 */
export function MoreMenu({
  label,
  children,
  className,
}: {
  /** The button's accessible name, e.g. "More actions for Asha". */
  label: string;
  children: ReactNode;
  className?: string;
}) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    function onKey(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      // Keep the page's own Escape (Home goes back to the composer) out of it.
      event.preventDefault();
      setOpen(false);
      buttonRef.current?.focus();
    }
    // Capture phase, so this runs before the page's own Escape handlers.
    document.addEventListener("keydown", onKey, true);
    return () => document.removeEventListener("keydown", onKey, true);
  }, [open]);

  return (
    <div className={cx("relative", className)}>
      <button
        ref={buttonRef}
        type="button"
        aria-label={label}
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((current) => !current)}
        className="rounded-control border-line text-ink lg:hover:bg-panel inline-flex size-11 items-center justify-center border pointer-fine:size-9"
      >
        <svg
          aria-hidden
          focusable="false"
          viewBox="0 0 24 24"
          className="size-5"
          fill="currentColor"
        >
          <circle cx="5" cy="12" r="1.8" />
          <circle cx="12" cy="12" r="1.8" />
          <circle cx="19" cy="12" r="1.8" />
        </svg>
      </button>
      {open ? (
        <div
          id={id}
          className="border-line bg-bg rounded-panel absolute top-full right-0 z-20 mt-2 flex w-[min(22rem,calc(100vw-2rem))] flex-col items-start gap-2 border p-3"
        >
          {children}
        </div>
      ) : null}
    </div>
  );
}
