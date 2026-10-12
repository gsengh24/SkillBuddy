import { brand } from "@/lib/brand";

import { cx } from "../ui/cx";

/**
 * The logo: the four-arc mark (green and ink, so mint and light in the dark theme) and the
 * lowercase wordmark, as drawn in the Home reference. The only place the logo is drawn, so
 * the real SVG (frontend/public/logo.svg, when it arrives) replaces it here.
 */
export function Logo({ className }: { className?: string }) {
  return (
    <span className={cx("text-ink inline-flex items-center gap-2", className)}>
      <LogoMark />
      <span className="font-display text-[20px] leading-none font-extrabold tracking-[-0.04em] lowercase">
        {brand.wordmark}
      </span>
    </span>
  );
}

/** The four-arc mark alone (decorative), for places that carry their own label. */
export function LogoMark({ className = "size-6 shrink-0" }: { className?: string }) {
  const green = "var(--green)";
  const ink = "var(--ink)";
  return (
    <svg aria-hidden focusable="false" viewBox="-44.1 -44.1 88.2 88.2" className={className}>
      <circle cx="-22.63" cy="-22.63" r="7.5" fill={green} />
      <path
        d="M-5.69 -24.11A17 17 0 0 1 -39.37 -19.68"
        fill="none"
        stroke={green}
        strokeWidth="6.5"
        strokeLinecap="round"
      />
      <circle cx="22.63" cy="-22.63" r="7.5" fill={ink} />
      <path
        d="M24.11 -5.69A17 17 0 0 1 19.68 -39.37"
        fill="none"
        stroke={ink}
        strokeWidth="6.5"
        strokeLinecap="round"
      />
      <circle cx="22.63" cy="22.63" r="7.5" fill={green} />
      <path
        d="M5.69 24.11A17 17 0 0 1 39.37 19.68"
        fill="none"
        stroke={green}
        strokeWidth="6.5"
        strokeLinecap="round"
      />
      <circle cx="-22.63" cy="22.63" r="7.5" fill={ink} />
      <path
        d="M-24.11 5.69A17 17 0 0 1 -19.68 39.37"
        fill="none"
        stroke={ink}
        strokeWidth="6.5"
        strokeLinecap="round"
      />
    </svg>
  );
}
