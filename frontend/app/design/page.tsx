import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { isStyleGuideEnabled } from "@/lib/env";

import { StyleGuide } from "./style-guide";

export const metadata: Metadata = {
  title: "Design system",
  robots: { index: false, follow: false },
};

/**
 * The style guide: in development and on Vercel preview deployments only. Production
 * answers 404. There is no sitemap; if one is added, leave this page out of it.
 */
export default function DesignPage() {
  if (!isStyleGuideEnabled()) notFound();
  return <StyleGuide />;
}
