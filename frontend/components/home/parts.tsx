import Image from "next/image";
import Link from "next/link";

import { ButtonLink } from "@/components/ds/button";
import { cx } from "@/components/ui/cx";

/** Three bordered cells: a mono label over a large numeral. Counts come from data already loaded. */
export function SummaryStrip({
  counts,
  className,
}: {
  counts: { requests: number; messages: number; connections: number };
  className?: string;
}) {
  const cells = [
    { label: "Requests", value: counts.requests, hint: "open requests" },
    { label: "Messages", value: counts.messages, hint: "unread messages" },
    { label: "Connections", value: counts.connections, hint: "connections" },
  ];
  return (
    <dl
      aria-label="Summary"
      className={cx("border-line grid grid-cols-3 gap-2 rounded-[14px] border p-[18px]", className)}
    >
      {cells.map((cell) => (
        <div key={cell.label} className="grid gap-1.5">
          <dt className="text-muted font-mono text-[11px] leading-[1.4] font-medium tracking-[0.08em] uppercase">
            {cell.label}
            <span className="sr-only"> ({cell.hint})</span>
          </dt>
          <dd className="font-display text-[34px] leading-none font-extrabold tracking-[-0.04em] tabular-nums">
            {cell.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

/** The green band under the composer: from a connection to a shared goal. */
export function SpacesBand({ className }: { className?: string }) {
  return (
    <div
      className={cx(
        "bg-green relative flex items-stretch gap-3.5 overflow-hidden rounded-[14px] p-[18px]",
        className,
      )}
    >
      <div className="flex flex-col justify-between gap-3.5">
        <h2 className="font-display text-bg max-w-[18ch] text-[19px] leading-[1.15] font-bold tracking-[-0.02em]">
          Turn a connection <span className="text-mint-text">into a shared goal.</span>
        </h2>
        <ButtonLink
          href="/teams"
          variant="white"
          size="compact"
          className="self-start rounded-[10px] font-semibold"
        >
          Open pair spaces
        </ButtonLink>
      </div>
      <Image
        src="/art/home/home_pair_space.jpg"
        alt=""
        width={170}
        height={170}
        unoptimized
        className="ml-auto aspect-square w-[42%] max-w-[170px] self-center rounded-[10px] object-cover"
      />
    </div>
  );
}

/** Shown in the detail pane when an item in the link no longer exists for this person. */
export function NotAvailable() {
  return (
    <div className="flex flex-col items-start gap-3 py-6">
      <p className="text-ink">This isn&apos;t available any more.</p>
      <Link
        href="/home"
        className="border-line-strong text-ink inline-flex min-h-11 items-center rounded-[10px] border px-3.5 text-[14px] font-semibold"
      >
        Back to Home
      </Link>
    </div>
  );
}
