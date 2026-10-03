import { NextResponse, type NextRequest } from "next/server";

import { SESSION_COOKIE } from "@/lib/auth/constants";

/**
 * Next.js Proxy (formerly "middleware"): sends signed-out visitors of protected pages to
 * /login before any rendering happens.
 *
 * It only checks that a session cookie exists; each protected page then verifies the session
 * with the API (`getCurrentUser`) and redirects again if it is invalid or expired.
 */
export function proxy(request: NextRequest) {
  if (request.cookies.has(SESSION_COOKIE)) return NextResponse.next();
  const login = new URL("/login", request.url);
  login.searchParams.set("next", `${request.nextUrl.pathname}${request.nextUrl.search}`);
  return NextResponse.redirect(login);
}

export const config = {
  matcher: [
    "/home/:path*",
    "/messages/:path*",
    "/saved/:path*",
    "/notifications/:path*",
    "/settings/:path*",
    "/moderation/:path*",
  ],
};
