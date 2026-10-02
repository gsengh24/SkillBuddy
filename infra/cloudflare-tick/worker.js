// Skill Buddy scheduler (ADR 0008): a Cloudflare Worker with two cron triggers that calls the
// API's tick endpoint, which enqueues the daily and hourly background jobs.
//
// Paste this file into the Worker's editor in the Cloudflare dashboard (steps in
// docs/deployment-plan.md). It needs two settings on the Worker:
//   API_URL          (text)   the API's public URL, e.g. https://skillbuddy-api.onrender.com
//   JOBS_TICK_TOKEN  (secret) the same value as JOBS_TICK_TOKEN on the API host
//
// Cron triggers (UTC): "30 2-17 * * *" (hourly 08:00-23:00 IST) and "30 0 * * *" (06:00 IST).
// A free Render API sleeps when idle and takes about a minute to wake, so the call waits up
// to two minutes and tries once more after a short pause.

const WAIT_MS = 120_000;
const RETRY_AFTER_MS = 20_000;

export async function tick(env, { fetchImpl = fetch, sleep = defaultSleep } = {}) {
  if (!env.API_URL || !env.JOBS_TICK_TOKEN) {
    throw new Error("API_URL and JOBS_TICK_TOKEN must be set on the Worker");
  }
  const url = `${env.API_URL.replace(/\/+$/, "")}/api/v1/admin/jobs/tick`;
  let lastError = "no attempt";
  for (let attempt = 1; attempt <= 2; attempt += 1) {
    try {
      const response = await fetchImpl(url, {
        method: "POST",
        headers: { "X-Jobs-Tick-Token": env.JOBS_TICK_TOKEN },
        signal: AbortSignal.timeout(WAIT_MS),
      });
      if (response.ok) {
        const body = await response.json();
        console.log(
          `tick ok: enqueued=${body.enqueued.join(",") || "-"} ` +
            `already=${body.already_enqueued.join(",") || "-"}`,
        );
        return body;
      }
      lastError = `HTTP ${response.status}`;
      // 403/404 mean a wrong token or the endpoint is off: retrying will not help.
      if (response.status === 403 || response.status === 404) break;
    } catch (error) {
      lastError = error instanceof Error ? error.name : "error";
    }
    if (attempt === 1) await sleep(RETRY_AFTER_MS);
  }
  // Never log the token; the status is enough to diagnose.
  throw new Error(`tick failed: ${lastError}`);
}

function defaultSleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export default {
  async scheduled(_event, env, ctx) {
    ctx.waitUntil(tick(env));
  },
  // Visiting the Worker's URL does nothing useful; it only runs on its schedule.
  async fetch() {
    return new Response("Skill Buddy scheduler: runs on cron triggers only.\n", {
      status: 404,
    });
  },
};
