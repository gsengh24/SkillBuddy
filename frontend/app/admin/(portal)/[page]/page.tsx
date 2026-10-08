import { notFound } from "next/navigation";

import { ComingNext } from "@/components/admin/admin-shell";
import { pageBySlug } from "@/lib/admin/pages";
import { getAdminMe } from "@/lib/admin/server";

type Props = { params: Promise<{ page: string }> };

/** Sidebar pages built in later admin steps. A role without the page's permission gets 404. */
export default async function AdminComingNextPage({ params }: Props) {
  const [{ page: slug }, me] = await Promise.all([params, getAdminMe()]);
  const page = pageBySlug(slug);
  if (!page || !page.slug || !me.permissions.includes(page.permission)) notFound();
  return <ComingNext label={page.label} />;
}
