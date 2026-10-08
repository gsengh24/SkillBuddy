import type { Metadata } from "next";
import type { ReactNode } from "react";

/** The admin portal (ADR 0015): its own layout, never indexed, not linked from the app. */
export const metadata: Metadata = {
  title: { template: "%s · Admin", default: "Admin" },
  robots: { index: false, follow: false, nocache: true },
};

export default function AdminRootLayout({ children }: { children: ReactNode }) {
  return children;
}
