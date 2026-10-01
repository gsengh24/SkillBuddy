import { hueStyle, personHue } from "@/lib/design/color";

import { cx } from "./cx";

const SIZES = {
  sm: "size-8 text-[12px]",
  md: "size-10 text-[14px]",
  lg: "size-14 text-[18px]",
} as const;

/** Up to two initials from a name or, failing that, an email address's local part. */
export function initialsFor(name: string): string {
  const source = name.includes("@") ? (name.split("@")[0] ?? "") : name;
  const words = source.split(/[\s._-]+/).filter(Boolean);
  return words
    .slice(0, 2)
    .map((word) => word[0] ?? "")
    .join("")
    .toUpperCase();
}

type AvatarProps = {
  /** Picks the colour: a stable hash of the id, never anything about the person. */
  userId: string;
  name: string;
  size?: keyof typeof SIZES;
  /** Hide from assistive technology when the name is already shown next to it. */
  decorative?: boolean;
  className?: string;
};

/** Initials on the person's tint, in that hue's ink. Round. */
export function Avatar({ userId, name, size = "md", decorative = false, className }: AvatarProps) {
  return (
    <span
      role={decorative ? undefined : "img"}
      aria-label={decorative ? undefined : name}
      aria-hidden={decorative || undefined}
      style={hueStyle(personHue(userId))}
      className={cx(
        "inline-flex shrink-0 items-center justify-center rounded-full bg-(--hue-tint) font-bold text-(--hue-ink)",
        SIZES[size],
        className,
      )}
    >
      {initialsFor(name)}
    </span>
  );
}
