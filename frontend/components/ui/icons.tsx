import type { ReactNode } from "react";

/** Thin-stroke 20px icons. Always decorative: the control next to them carries the label. */
function Icon({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <svg
      aria-hidden
      focusable="false"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className ?? "size-5"}
    >
      {children}
    </svg>
  );
}

export function CompassIcon({ className }: { className?: string }) {
  return (
    <Icon className={className}>
      <circle cx="12" cy="12" r="9" />
      <path d="m15.5 8.5-2 5-5 2 2-5z" />
    </Icon>
  );
}

export function MessageIcon({ className }: { className?: string }) {
  return (
    <Icon className={className}>
      <path d="M5 5h14v10H9l-4 4z" />
    </Icon>
  );
}

export function BookmarkIcon({ className }: { className?: string }) {
  return (
    <Icon className={className}>
      <path d="M7 4h10v16l-5-4-5 4z" />
    </Icon>
  );
}

export function PersonIcon({ className }: { className?: string }) {
  return (
    <Icon className={className}>
      <circle cx="12" cy="8" r="3.5" />
      <path d="M5 20c1-4 4-6 7-6s6 2 7 6" />
    </Icon>
  );
}

export function BellIcon({ className }: { className?: string }) {
  return (
    <Icon className={className}>
      <path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15z" />
      <path d="M10 20a2 2 0 0 0 4 0" />
    </Icon>
  );
}

export function RingsIcon({ className }: { className?: string }) {
  return (
    <Icon className={className}>
      <circle cx="9" cy="12" r="5" />
      <circle cx="15" cy="12" r="5" />
    </Icon>
  );
}
