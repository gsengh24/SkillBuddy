import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { StyleGuide } from "./style-guide";

export const metadata: Metadata = { title: "Design system", robots: { index: false } };

/** The style guide: development only. Production builds answer 404. */
export default function DesignPage() {
  if (process.env.NODE_ENV === "production") notFound();
  return <StyleGuide />;
}
