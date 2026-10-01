import { cx } from "./cx";

type BadgeProps = {
  count: number;
  /** What is being counted, for screen readers, e.g. "unread messages". */
  label: string;
  className?: string;
};

/**
 * A filled count badge. Uses the darker badge coral (#B83D28): the coral base under paper
 * text is only 3.71:1. Renders nothing at zero. Counts above 99 show "99+".
 */
export function Badge({ count, label, className }: BadgeProps) {
  if (count <= 0) return null;
  return (
    <span
      className={cx(
        "bg-badge text-badge-text inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 text-[11px] leading-none font-bold",
        className,
      )}
    >
      <span aria-hidden>{count > 99 ? "99+" : count}</span>
      <span className="sr-only">{`${count} ${label}`}</span>
    </span>
  );
}

/**
 * A small dot meaning "something new". Give it a label (read by screen readers only), or
 * leave it out when the control it sits on already says so; it is then hidden.
 */
export function BadgeDot({ label, className }: { label?: string; className?: string }) {
  return (
    <span
      aria-hidden={label ? undefined : true}
      className={cx("bg-badge inline-block size-2 rounded-full", className)}
    >
      {label ? <span className="sr-only">{label}</span> : null}
    </span>
  );
}
