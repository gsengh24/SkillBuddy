import type { NextConfig } from "next";

import { securityHeaders } from "./lib/security-headers";

const nextConfig: NextConfig = {
  // Self-contained server bundle for the production Docker image.
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
  // The landing page and the team page are self-contained static documents
  // (public/landing, public/team).
  async rewrites() {
    return {
      beforeFiles: [
        { source: "/", destination: "/landing/index.html" },
        { source: "/team", destination: "/team/index.html" },
      ],
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
