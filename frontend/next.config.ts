import type { NextConfig } from "next";

import { securityHeaders } from "./lib/security-headers";

const nextConfig: NextConfig = {
  // Self-contained server bundle for the production Docker image.
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
  // No dev-only route badge: it sits over fixed bottom bars (onboarding's Edit button on a
  // phone) and blocks clicks in the Smoke tests. Compile and runtime errors still show.
  devIndicators: false,
  // The landing page is a self-contained static document (public/landing).
  async rewrites() {
    return {
      beforeFiles: [{ source: "/", destination: "/landing/index.html" }],
      afterFiles: [],
      fallback: [],
    };
  },
  async headers() {
    const isDev = process.env.NODE_ENV !== "production";
    return [{ source: "/:path*", headers: securityHeaders(isDev) }];
  },
};

export default nextConfig;
