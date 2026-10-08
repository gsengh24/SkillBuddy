import type { Metadata } from "next";

import { ComingNext } from "@/components/admin/admin-shell";

export const metadata: Metadata = { title: "Overview" };

export default function AdminOverviewPage() {
  return <ComingNext label="Overview" />;
}
