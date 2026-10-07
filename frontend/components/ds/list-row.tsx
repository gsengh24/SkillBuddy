import Link from "next/link";
import type { ReactNode } from "react";

import { cx } from "../ui/cx";
import { SearchIcon, UserPlusIcon } from "./icons";

type ListRowProps = {
  /** Where the row goes. Rows are links: opening one changes the URL. */
  href: string;
  /** A 34px leading tile or avatar (decorative: the title names the row). */
  leading: ReactNode;
  title: string;
  /** One line under the title. */
  secondary?: string;
  /** Relative time, e.g. "2m", "Yesterday". */
  time?: string;
  /** A StatusBadge or similar, on the right. */
  badge?: ReactNode;
  /** Shows the unread dot; screen readers hear `unreadLabel`. */
  unread?: boolean;
  unreadLabel?: string;
  /** The row whose detail is open (desktop two-column layout). */
  selected?: boolean;
  className?: string;
};

/**
 * One row of a list: leading tile, title (14px, 600), one line of secondary text, and on
 * the right a mono time with a badge or unread dot. Rows are separated by hairlines, not
 * drawn as cards. At least 56px high.
 */
export function ListRow({
  href,
  leading,
  title,
  secondary,
  time,
  badge,
  unread = false,
  unreadLabel = "Unread",
  selected = false,
  className,
}: ListRowProps) {
  return (
    <li className="border-line border-b">
      <Link
        href={href}
        aria-current={selected ? "true" : undefined}
        className={cx(
          "lg:hover:bg-panel flex min-h-14 gap-2.5 px-1 py-3",
          selected && "lg:bg-green-tint lg:hover:bg-green-tint",
          className,
        )}
      >
        <span aria-hidden className="shrink-0">
          {leading}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex justify-between gap-2">
            <span className="text-title truncate">{title}</span>
            <span className="flex h-fit shrink-0 items-center gap-2">
              {time ? <span className="text-mono text-muted font-mono">{time}</span> : null}
              {badge}
              {unread ? (
                <span className="bg-green inline-block size-2 shrink-0 rounded-full">
                  <span className="sr-only">{unreadLabel}</span>
                </span>
              ) : null}
            </span>
          </span>
          {secondary ? (
            <span className={cx("text-meta block truncate", unread ? "text-ink" : "text-muted")}>
              {secondary}
            </span>
          ) : null}
        </span>
      </Link>
    </li>
  );
}

/** The 34px leading tile of a request row (search icon) or intro row (dashed, user-plus). */
export function RowTile({ kind }: { kind: "request" | "intro" }) {
  return (
    <span
      className={cx(
        "text-green inline-flex size-[34px] items-center justify-center rounded-[9px]",
        kind === "request"
          ? "bg-green-tint border-green-line border"
          : "bg-bg border-green border border-dashed",
      )}
    >
      {kind === "request" ? <SearchIcon /> : <UserPlusIcon />}
    </span>
  );
}
