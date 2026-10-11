import { describe, expect, it } from "vitest";

import { clientIpFromHeaders } from "./client-ip";

describe("clientIpFromHeaders", () => {
  it("ignores addresses the visitor put on the left of the chain", () => {
    expect(clientIpFromHeaders("6.6.6.6, 203.0.113.9", null, 1)).toBe("203.0.113.9");
  });

  it("counts trusted hops from the right", () => {
    expect(clientIpFromHeaders("6.6.6.6, 203.0.113.9, 10.0.0.2", null, 2)).toBe("203.0.113.9");
  });

  it("falls back to x-real-ip when there is no usable chain", () => {
    expect(clientIpFromHeaders(null, "198.51.100.4", 1)).toBe("198.51.100.4");
    expect(clientIpFromHeaders("203.0.113.9", "198.51.100.4", 2)).toBe("198.51.100.4");
  });

  it("rejects values that are not IP addresses", () => {
    expect(clientIpFromHeaders("not-an-ip", null, 1)).toBeUndefined();
    expect(clientIpFromHeaders("1.2.3.4, evil\r\nx: y", null, 1)).toBeUndefined();
  });

  it("accepts IPv6", () => {
    expect(clientIpFromHeaders("2001:db8::1", null, 1)).toBe("2001:db8::1");
  });
});
