import { ButtonLink } from "@/components/ds/button";
import { PixelPattern } from "@/components/ds/pixel-pattern";
import { cx } from "@/components/ui/cx";

/** Three bordered cells: a large numeral over a mono label. Counts come from data already loaded. */
export function SummaryStrip({
  counts,
}: {
  counts: { requests: number; messages: number; spaces: number };
}) {
  const cells = [
    { label: "Requests", value: counts.requests, hint: "open requests" },
    { label: "Messages", value: counts.messages, hint: "unread messages" },
    { label: "Spaces", value: counts.spaces, hint: "pair spaces" },
  ];
  return (
    <dl
      aria-label="Summary"
      className="border-line rounded-panel grid grid-cols-3 overflow-hidden border"
    >
      {cells.map((cell) => (
        <div
          key={cell.label}
          className="border-line flex flex-col-reverse border-r px-3.5 py-3 last:border-r-0"
        >
          <dt className="text-mono text-muted mt-1.5 font-mono uppercase">
            {cell.label}
            <span className="sr-only"> ({cell.hint})</span>
          </dt>
          <dd className="font-display tracking-display text-[28px] leading-none font-extrabold">
            {cell.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

/** The green band under the list: from a connection to a shared goal. */
export function SpacesBand({ className }: { className?: string }) {
  return (
    <div
      className={cx("bg-green rounded-panel relative overflow-hidden px-4 py-[18px]", className)}
    >
      <h2 className="font-display text-bg tracking-display mb-3.5 max-w-[230px] text-[20px] leading-[1.05] font-extrabold">
        Turn a connection <span className="text-mint-text">into a shared goal.</span>
      </h2>
      <ButtonLink href="/spaces" variant="white" size="compact">
        Open pair spaces
      </ButtonLink>
      <PixelPattern onGreen className="absolute right-3.5 bottom-3" />
    </div>
  );
}

/** Shown in the detail pane when an item in the link no longer exists for this person. */
export function NotAvailable() {
  return (
    <div className="flex flex-col items-start gap-3 py-6">
      <p className="text-ink">This isn&apos;t available any more.</p>
      <ButtonLink href="/home" variant="outline">
        Back to Home
      </ButtonLink>
    </div>
  );
}
