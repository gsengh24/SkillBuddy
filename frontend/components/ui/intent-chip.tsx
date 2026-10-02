import { hueStyle } from "@/lib/design/color";
import { intents, type Intent } from "@/lib/design/tokens";

import { cx } from "./cx";

type IntentChipProps = {
  intent: Intent;
  /** Selected: paper fill and a border in the intent's colour (its ink, for 3:1 contrast). */
  selected?: boolean;
  /** Makes the chip a toggle button (aria-pressed). Without it the chip is static. */
  onToggle?: () => void;
  className?: string;
};

/** An intent as a pill: a colour dot plus its name. The label carries the meaning. */
export function IntentChip({ intent, selected = false, onToggle, className }: IntentChipProps) {
  const { label, hue } = intents[intent];
  const classes = cx(
    "inline-flex items-center gap-2 rounded-full border px-3.5 text-small font-semibold text-ink",
    selected ? "border-(--hue-ink) bg-paper" : "border-green-chip-edge bg-green-chip",
    className,
  );
  const content = (
    <>
      <span aria-hidden className="size-2 shrink-0 rounded-full bg-(--hue-base)" />
      {label}
    </>
  );
  if (onToggle) {
    return (
      <button
        type="button"
        aria-pressed={selected}
        onClick={onToggle}
        style={hueStyle(hue)}
        className={cx(classes, "hover:bg-paper h-11 lg:pointer-fine:h-9")}
      >
        {content}
      </button>
    );
  }
  return (
    <span style={hueStyle(hue)} className={cx(classes, "h-9")}>
      {content}
    </span>
  );
}
