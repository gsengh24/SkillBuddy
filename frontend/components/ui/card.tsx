import type { ComponentProps } from "react";

import { cx } from "./cx";

/** Paper surface with a 1px line border and radius 18. */
export function Card({ className, ...props }: ComponentProps<"div">) {
  return (
    <div className={cx("rounded-card border-line bg-paper border p-5", className)} {...props} />
  );
}
