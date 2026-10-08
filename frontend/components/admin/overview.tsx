import Link from "next/link";

import { cx } from "@/components/ui/cx";
import type { Health, Overview } from "@/lib/admin/schemas";

const KPI_LABELS: Record<string, string> = {
  new_signups: "New sign-ups",
  active_users: "Active users",
  new_requests: "New requests",
  matches_made: "Matches made",
  intro_accept_rate: "Intro accept rate",
  messages_sent: "Messages sent",
};

const FUNNEL_LABELS: Record<string, string> = {
  requests: "Requests",
  matches: "Matches",
  intros_sent: "Intros sent",
  intros_accepted: "Intros accepted",
  chats_started: "Chats started",
};

/** Each "needs attention" row and where it is handled. */
const ATTENTION: Record<string, { label: string; href: string }> = {
  open_reports: { label: "Open reports", href: "/admin/reports" },
  pending_applications: { label: "Applications waiting", href: "/admin/access" },
  degraded_ai_providers: { label: "AI providers failing", href: "/admin/ai" },
  due_data_requests: { label: "Data requests waiting", href: "/admin/data" },
  failed_emails: { label: "Emails that failed (7 days)", href: "/admin/comms" },
};

function delta(value: number, previous: number, percent: boolean): { text: string; up: boolean } {
  if (percent) {
    const points = Math.round((value - previous) * 10) / 10;
    return { text: `${points >= 0 ? "+" : ""}${points} pts`, up: points >= 0 };
  }
  if (!previous) return { text: value ? "new" : "no change", up: true };
  const change = Math.round(((value - previous) / previous) * 100);
  return { text: `${change >= 0 ? "+" : ""}${change}%`, up: change >= 0 };
}

export function Kpis({ overview }: { overview: Overview }) {
  return (
    <ul aria-label="Key figures" className="grid grid-cols-2 gap-2.5 md:grid-cols-3 lg:grid-cols-6">
      {overview.kpis.map((kpi) => {
        const percent = kpi.key === "intro_accept_rate";
        const change = delta(kpi.value, kpi.previous, percent);
        return (
          <li
            key={kpi.key}
            className="border-line bg-bg rounded-panel flex flex-col gap-3.5 border p-3.5"
          >
            <span className="text-mono text-muted font-mono uppercase">
              {KPI_LABELS[kpi.key] ?? kpi.key}
            </span>
            <span className="font-display tracking-display text-[26px] leading-none font-extrabold">
              {percent ? `${kpi.value}%` : kpi.value.toLocaleString()}
            </span>
            <span className={cx("font-mono text-[11px]", change.up ? "text-green" : "text-danger")}>
              {change.text} vs previous {overview.days} days
            </span>
          </li>
        );
      })}
    </ul>
  );
}

/** Sign-ups per day as bars, in plain SVG (no chart library). */
export function SignupChart({ overview }: { overview: Overview }) {
  const points = overview.signups_by_day;
  const max = Math.max(1, ...points.map((p) => p.count));
  const width = 600;
  const height = 160;
  const gap = 2;
  const bar = Math.max(1, width / points.length - gap);
  const total = points.reduce((sum, p) => sum + p.count, 0);
  return (
    <figure className="flex flex-col gap-2">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`Sign-ups per day: ${total} in the last ${overview.days} days, at most ${max} in a day.`}
        className="h-auto w-full"
      >
        <line x1="0" y1={height - 0.5} x2={width} y2={height - 0.5} className="stroke-line" />
        {points.map((point, index) => {
          const h = (point.count / max) * (height - 8);
          return (
            <rect
              key={point.day}
              x={index * (bar + gap)}
              y={height - h}
              width={bar}
              height={h}
              rx="2"
              className="fill-green"
            >
              <title>{`${point.day}: ${point.count}`}</title>
            </rect>
          );
        })}
      </svg>
      <figcaption className="text-meta text-muted flex justify-between font-mono">
        <span>{points[0]?.day}</span>
        <span>{points.at(-1)?.day}</span>
      </figcaption>
    </figure>
  );
}

export function Funnel({ overview }: { overview: Overview }) {
  const top = Math.max(1, overview.funnel[0]?.count ?? 0, ...overview.funnel.map((s) => s.count));
  return (
    <ul aria-label="From request to chat" className="flex flex-col gap-2.5">
      {overview.funnel.map((step) => (
        <li
          key={step.step}
          className="text-meta grid grid-cols-[110px_1fr_56px] items-center gap-2.5"
        >
          <span>{FUNNEL_LABELS[step.step] ?? step.step}</span>
          <span className="bg-line block h-2.5 overflow-hidden rounded-full">
            <span
              className="bg-green block h-full rounded-full"
              style={{ width: `${(step.count / top) * 100}%` }}
            />
          </span>
          <span className="text-right font-mono">{step.count.toLocaleString()}</span>
        </li>
      ))}
    </ul>
  );
}

export function Attention({ overview }: { overview: Overview }) {
  return (
    <ul className="divide-line flex flex-col divide-y">
      {Object.entries(ATTENTION).map(([key, { label, href }]) => {
        const count = overview.attention[key] ?? 0;
        return (
          <li key={key}>
            <Link
              href={href}
              aria-label={`${label}: ${count}`}
              className="hover:bg-panel flex min-h-11 items-center gap-3 rounded-lg px-1 py-2"
            >
              <span className="font-display tracking-display min-w-[34px] text-[22px] font-extrabold">
                {count}
              </span>
              <span className={cx("flex-1", count ? "text-ink" : "text-muted")}>{label}</span>
              <span aria-hidden className="text-muted">
                ›
              </span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

const DOT: Record<string, string> = { ok: "bg-green", warn: "bg-amber-base", down: "bg-danger" };

export function HealthList({ health }: { health: Health }) {
  return (
    <ul className="divide-line flex flex-col divide-y">
      {health.checks.map((check) => (
        <li key={check.name} className="flex items-center gap-3 py-2.5">
          <span
            aria-hidden
            className={cx("size-2.5 shrink-0 rounded-full", DOT[check.status] ?? "bg-muted")}
          />
          <span className="flex-1">
            <span className="font-semibold">{check.name}</span>
            <span className="text-meta text-muted block">{check.detail}</span>
          </span>
          <span className="text-mono text-muted font-mono uppercase">{check.status}</span>
        </li>
      ))}
    </ul>
  );
}
