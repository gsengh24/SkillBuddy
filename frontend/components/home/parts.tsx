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
      className="border-line rounded-card mt-3 grid grid-cols-3 overflow-hidden border"
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
          <dd className="font-display text-[26px] leading-none font-extrabold tracking-[-0.05em]">
            {cell.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

/** "Start your first request": the empty state, with a way to start. */
export function StartFirstRequest({
  href,
  className,
}: {
  /** Where "Find people" goes: the composer, or onboarding before there is a profile. */
  href: string;
  className?: string;
}) {
  return (
    <div className={cx("flex flex-col items-start gap-3 py-6", className)}>
      <h2 className="font-display text-headline">Start your first request</h2>
      <p className="text-ink-2 max-w-[46ch]">
        Say what you&apos;re building in a sentence, and we&apos;ll find people who can help.
      </p>
      <ButtonLink href={href} variant="primary">
        Find people
      </ButtonLink>
    </div>
  );
}

/** The green band under the list: from a connection to a shared goal. */
export function SpacesBand() {
  return (
    <div className="bg-green rounded-panel relative mt-5 overflow-hidden px-4 py-[18px]">
      <h2 className="font-display text-bg mb-3.5 max-w-[230px] text-[22px] leading-none font-extrabold tracking-[-0.05em]">
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
