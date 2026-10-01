import { hues } from "@/lib/design/tokens";

const RINGS = [
  { cx: 60, cy: 62, color: hues.green.base },
  { cx: 102, cy: 46, color: hues.amber.base },
  { cx: 140, cy: 82, color: hues.coral.base },
  { cx: 92, cy: 104, color: hues.blue.base },
  { cx: 178, cy: 56, color: hues.violet.base },
];

/** The "pairing rings" motif: overlapping thin rings. Decorative only. */
export function PairingRings({ className }: { className?: string }) {
  return (
    <svg aria-hidden focusable="false" viewBox="0 0 230 150" fill="none" className={className}>
      {RINGS.map((ring) => (
        <circle
          key={`${ring.cx}-${ring.cy}`}
          cx={ring.cx}
          cy={ring.cy}
          r={38}
          stroke={ring.color}
          strokeWidth={1.25}
        />
      ))}
    </svg>
  );
}
