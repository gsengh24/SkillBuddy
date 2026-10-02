/**
 * How often an open conversation asks for new messages (ADR 0012): fast right after a
 * message, slower as it goes quiet, and not at all after 10 quiet minutes, so a forgotten
 * tab never keeps the database awake.
 */
const STEPS: readonly { quietUnderMs: number; delayMs: number }[] = [
  { quietUnderMs: 60_000, delayMs: 3_000 },
  { quietUnderMs: 5 * 60_000, delayMs: 10_000 },
  { quietUnderMs: 10 * 60_000, delayMs: 30_000 },
];

/** Milliseconds until the next poll, or null to stop until the person is back. */
export function nextPollDelay(
  quietMs: number,
  serverMinimumSeconds?: number | null,
): number | null {
  const step = STEPS.find(({ quietUnderMs }) => quietMs < quietUnderMs);
  if (!step) return null;
  return Math.max(step.delayMs, (serverMinimumSeconds ?? 0) * 1000);
}

/** After a failed poll: honour Retry-After, otherwise back off to a minute. */
export function delayAfterError(retryAfterSeconds?: number): number {
  return Math.max(retryAfterSeconds ?? 60, 3) * 1000;
}
