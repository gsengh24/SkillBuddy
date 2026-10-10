import { avatarFill } from "@/lib/design/color";

import { initialsFor } from "../ui/avatar";
import { cx } from "../ui/cx";

const SIZES = {
  sm: "size-7 text-[11px]",
  md: "size-[34px] text-[13px]",
  lg: "size-12 text-[16px]",
  xl: "font-display size-16 text-[22px] font-extrabold lg:size-20 lg:text-[28px]",
} as const;

const FILLS = { green: "bg-green", ink: "bg-ink" } as const;

type AvatarProps = {
  /** Picks the fill (green or ink): a stable hash of the id, never anything about the person. */
  userId: string;
  name: string;
  size?: keyof typeof SIZES;
  /**
   * The person's Google account picture (ADR 0017). The API sets it only for yourself and
   * for people you're connected with who chose to show it; never pass any other address.
   */
  photoUrl?: string | null;
  /** Hide from assistive technology when the name is already shown next to it. */
  decorative?: boolean;
  className?: string;
};

/**
 * A circle with initials: white on green or ink. A picture, when there is one, lies over
 * the initials, so they still show if it fails to load.
 */
export function Avatar({
  userId,
  name,
  size = "md",
  photoUrl,
  decorative = false,
  className,
}: AvatarProps) {
  return (
    <span
      role={decorative ? undefined : "img"}
      aria-label={decorative ? undefined : name}
      aria-hidden={decorative || undefined}
      data-fill={avatarFill(userId)}
      className={cx(
        "text-bg relative inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full font-medium",
        FILLS[avatarFill(userId)],
        SIZES[size],
        className,
      )}
    >
      {initialsFor(name)}
      {photoUrl ? (
        // Plain <img>, not next/image: the picture is already small and stays on Google's
        // servers; the optimiser would fetch and re-serve it from ours. The empty alt keeps
        // a failed picture invisible, and Google is not told which page asked.
        // eslint-disable-next-line @next/next/no-img-element -- see the comment above
        <img
          src={photoUrl}
          alt=""
          referrerPolicy="no-referrer"
          loading="lazy"
          decoding="async"
          className="absolute inset-0 size-full object-cover"
        />
      ) : null}
    </span>
  );
}
