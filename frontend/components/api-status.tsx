import { getApiStatus, type ApiStatus } from "@/lib/api/health";

const presentation: Record<ApiStatus["state"], { label: string; dot: string; text: string }> = {
  connected: { label: "API connected", dot: "bg-emerald-500", text: "text-emerald-700" },
  degraded: { label: "API degraded", dot: "bg-amber-500", text: "text-amber-700" },
  unreachable: { label: "API unreachable", dot: "bg-rose-500", text: "text-rose-700" },
};

/** Server component: checks API readiness on every request and renders the result. */
export async function ApiStatusIndicator() {
  const status = await getApiStatus();
  const { label, dot, text } = presentation[status.state];

  return (
    <div
      role="status"
      data-state={status.state}
      className="inline-flex flex-col gap-2 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm"
    >
      <span className={`inline-flex items-center gap-2 font-medium ${text}`}>
        <span aria-hidden className={`h-2.5 w-2.5 rounded-full ${dot}`} />
        {label}
      </span>
      {status.state === "unreachable" ? (
        <span className="text-slate-500">The web server could not reach the API.</span>
      ) : (
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-slate-600">
          {Object.entries(status.readiness.checks).map(([name, check]) => (
            <li key={name}>
              {name}:{" "}
              <span className={check.status === "ok" ? "text-emerald-700" : "text-rose-700"}>
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
    <div
      role="status"
      className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-500 shadow-sm"
    >
      <span aria-hidden className="h-2.5 w-2.5 animate-pulse rounded-full bg-slate-300" />
      Checking API…
    </div>
  );
}
