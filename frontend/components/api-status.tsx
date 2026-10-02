import { getApiStatus, type ApiStatus } from "@/lib/api/health";

const presentation: Record<ApiStatus["state"], { label: string; dot: string; text: string }> = {
  connected: { label: "API connected", dot: "bg-green-base", text: "text-green-ink" },
  degraded: { label: "API degraded", dot: "bg-amber-base", text: "text-amber-ink" },
  unreachable: { label: "API unreachable", dot: "bg-coral-base", text: "text-coral-ink" },
};

const CARD =
  "inline-flex flex-col gap-2 rounded-card border border-line bg-paper px-4 py-3 text-small";

/** Server component: checks API readiness on every request and renders the result. */
export async function ApiStatusIndicator() {
  const status = await getApiStatus();
  const { label, dot, text } = presentation[status.state];

  return (
    <div role="status" data-state={status.state} className={CARD}>
      <span className={`inline-flex items-center gap-2 font-semibold ${text}`}>
        <span aria-hidden className={`size-2.5 rounded-full ${dot}`} />
        {label}
      </span>
      {status.state === "unreachable" ? (
        <span className="text-muted">The web server could not reach the API.</span>
      ) : (
        <ul className="text-muted flex flex-wrap gap-x-4 gap-y-1">
          {Object.entries(status.readiness.checks).map(([name, check]) => (
            <li key={name}>
              {name}:{" "}
              <span className={check.status === "ok" ? "text-green-ink" : "text-coral-ink"}>
                {check.status}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function ApiStatusFallback() {
  return (
    <div role="status" className={`${CARD} text-muted flex-row items-center`}>
      <span aria-hidden className="bg-line-strong size-2.5 rounded-full" />
      Checking API…
    </div>
  );
}
