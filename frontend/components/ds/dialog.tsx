"use client";

import { useEffect, useId, useRef, type ReactNode } from "react";

import { cx } from "../ui/cx";

/**
 * A modal dialog on the native <dialog>: showModal() keeps focus inside it and makes the
 * page behind inert, Escape closes it, and the browser puts focus back where it was.
 * The owner keeps `open`; `onClose` runs on Escape and on every close.
 */
export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  className,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onCancel={(event) => {
        // Escape: let the owner close it, so `open` stays the source of truth.
        event.preventDefault();
        onClose();
      }}
      onClose={() => {
        if (open) onClose();
      }}
      className={cx(
        "border-line rounded-panel bg-bg text-ink m-auto w-[min(440px,calc(100vw-32px))] border p-0",
        "backdrop:bg-ink/45",
        className,
      )}
    >
      {open ? (
        <div className="flex flex-col gap-3 p-5">
          <h2
            id={titleId}
            className="font-display tracking-display text-[20px] leading-tight font-extrabold"
          >
            {title}
          </h2>
          {description ? <div className="text-meta-lg text-ink-2">{description}</div> : null}
          {children}
        </div>
      ) : null}
    </dialog>
  );
}
