import type { ComponentProps } from "react";

import { cx } from "./cx";
import { PairingRings } from "./pairing-rings";

/** The green hero panel (radius 22) with the pairing-rings motif behind its content. */
export function HeroPanel({ className, children, ...props }: ComponentProps<"div">) {
  return (
    <div
      className={cx("rounded-hero bg-green-panel text-ink relative overflow-hidden p-6", className)}
      {...props}
    >
      <PairingRings className="pointer-events-none absolute -top-4 -right-8 h-36 w-56" />
      <div className="relative flex flex-col gap-2">{children}</div>
    </div>
  );
}
