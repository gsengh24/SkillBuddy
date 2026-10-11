import { isIP } from "node:net";

/**
 * The visitor's address as seen by the nearest trusted proxy.
 *
 * `X-Forwarded-For` is `client, proxy1, proxy2`: every proxy appends the address it saw. Only
 * the entries our own proxies appended can be trusted, so we count from the right
 * (`trustedHops` = how many proxies sit in front of this server) and ignore anything the
 * visitor put on the left. Reading the leftmost entry would let anyone choose their own
 * address and dodge the API's per-IP rate limits (OWASP A04/A07).
 */
export function clientIpFromHeaders(
  forwardedFor: string | null,
  realIp: string | null,
  trustedHops: number,
): string | undefined {
  const chain = (forwardedFor ?? "")
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
  const candidate =
    chain.length >= trustedHops && trustedHops > 0 ? chain[chain.length - trustedHops] : realIp;
  const value = candidate?.trim();
  return value && isIP(value) !== 0 ? value : undefined;
}
