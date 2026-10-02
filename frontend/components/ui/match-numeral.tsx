import { hueStyle } from "@/lib/design/color";
import type { HueName } from "@/lib/design/tokens";

import { cx } from "./cx";

type MatchNumeralProps = {
  value: number;
  /** The person's hue; the numeral uses its ink (never its base). */
  hue?: HueName;
  className?: string;
};

/** The big match number: 33px, extra bold, tight letter-spacing, small "%". */
export function MatchNumeral({ value, hue = "green", className }: MatchNumeralProps) {
  const clamped = Math.max(0, Math.min(100, Math.round(value)));
  return (
    <p
      style={hueStyle(hue)}
      className={cx("text-numeral whitespace-nowrap text-(--hue-ink)", className)}
    >
      {clamped}
      <span className="text-small ml-0.5 font-bold">%</span>
      <span className="sr-only"> match</span>
    </p>
  );
}
