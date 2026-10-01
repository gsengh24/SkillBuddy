import { hueStyle } from "@/lib/design/color";
import type { HueName } from "@/lib/design/tokens";

import { cx } from "./cx";

type StrengthBarProps = {
  /** 0 to 100. */
  value: number;
  hue: HueName;
  /** Accessible name, e.g. "Match strength" or "Profile complete". */
  label: string;
  className?: string;
};

/** A ticked bar: track and fill in one hue. Exposed as a meter with its value. */
export function StrengthBar({ value, hue, label, className }: StrengthBarProps) {
  const clamped = Math.max(0, Math.min(100, Math.round(value)));
  return (
    <div
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={clamped}
      aria-valuetext={`${clamped}%`}
      style={hueStyle(hue)}
      className={cx("h-2 w-full overflow-hidden rounded-full bg-(--hue-track)", className)}
    >
      <div
        data-testid="strength-fill"
        className="h-full"
        style={{
          width: `${clamped}%`,
          backgroundImage:
            "repeating-linear-gradient(90deg, var(--hue-base) 0 6px, transparent 6px 8px)",
        }}
      />
    </div>
  );
}
