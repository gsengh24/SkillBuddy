import { avatarFill } from "@/lib/design/color";

import { initialsFor } from "../ui/avatar";
import { cx } from "../ui/cx";

const SIZES = {
  sm: "size-7 text-[11px]",
  md: "size-[34px] text-[13px]",
  lg: "size-12 text-[16px]",
} as const;

const FILLS = { green: "bg-green", ink: "bg-ink" } as const;

type AvatarProps = {
  /** Picks the fill (green or ink): a stable hash of the id, never anything about the person. */
  userId: string;
  name: string;
  size?: keyof typeof SIZES;
  /** Hide from assistive technology when the name is already shown next to it. */
  decorative?: boolean;
  className?: string;
};

/** A circle with initials: white on green or ink. No photos. */
export function Avatar({ userId, name, size = "md", decorative = false, className }: AvatarProps) {
  return (
    <span
      role={decorative ? undefined : "img"}
      aria-label={decorative ? undefined : name}
      aria-hidden={decorative || undefined}
      data-fill={avatarFill(userId)}
      className={cx(
        "text-bg inline-flex shrink-0 items-center justify-center rounded-full font-medium",
        FILLS[avatarFill(userId)],
        SIZES[size],
        className,
      )}
    >
      {initialsFor(name)}
    </span>
  );
}
