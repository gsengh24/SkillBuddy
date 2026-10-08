import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { AccessDenied, AdminShell } from "@/components/admin/admin-shell";
import { pagesFor } from "@/lib/admin/pages";
import { getAdminMe } from "@/lib/admin/server";
import { ApiError } from "@/lib/api/errors";
import { getCurrentUser } from "@/lib/auth/session";
import { deploymentLabel } from "@/lib/env";

export const dynamic = "force-dynamic";

/**
 * Every admin page: signed in, an admin, and past the second step. The API checks the
 * same on each call; this only decides what to show.
 */
export default async function AdminPortalLayout({ children }: { children: ReactNode }) {
  const user = await getCurrentUser();
  if (!user) redirect("/login?next=/admin");
  let me;
  try {
    me = await getAdminMe();
  } catch (error) {
    if (error instanceof ApiError && error.code === "admin_two_step_required") {
      redirect("/admin/two-step");
    }
    if (error instanceof ApiError && error.status === 403) {
      return <AccessDenied reason="This part of the site is for the team that runs it." />;
    }
    throw error;
  }

  return (
    <AdminShell
      pages={pagesFor(me.permissions)}
      role={me.role}
      name={me.name}
      environment={deploymentLabel()}
    >
      {children}
    </AdminShell>
  );
}
