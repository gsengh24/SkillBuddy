/**
 * The admin portal's pages, grouped as in reference-admin.html. Each page shows for the
 * roles that have its permission; the API checks the same permission on every request.
 */
export type AdminPage = {
  slug: string;
  label: string;
  group: string;
  permission: string;
};

export const ADMIN_PAGES: AdminPage[] = [
  { slug: "", label: "Overview", group: "", permission: "view_dashboards" },
  { slug: "users", label: "Users", group: "People", permission: "view_users" },
  { slug: "access", label: "Signup and access", group: "People", permission: "manage_signup" },
  { slug: "reports", label: "Reports and safety", group: "Safety", permission: "view_users" },
  { slug: "content", label: "Content moderation", group: "Safety", permission: "view_users" },
  { slug: "ai", label: "Matching and AI", group: "Platform", permission: "manage_ai" },
  { slug: "comms", label: "Communication", group: "Platform", permission: "manage_settings" },
  { slug: "settings", label: "Settings", group: "Platform", permission: "manage_settings" },
  { slug: "team", label: "Team and audit", group: "Admin", permission: "manage_admins" },
  { slug: "data", label: "Data and compliance", group: "Admin", permission: "delete_data" },
];

export function pagesFor(permissions: string[]): AdminPage[] {
  return ADMIN_PAGES.filter((page) => permissions.includes(page.permission));
}

/**
 * The counts shown beside menu entries, from the Overview's "needs attention" figures
 * (cached for a minute on the server). Zeroes are left out.
 */
export function menuCounts(attention: Record<string, number>): Record<string, number> {
  const counts: Record<string, number> = {
    reports: attention.open_reports ?? 0,
    access: attention.pending_applications ?? 0,
    data: attention.due_data_requests ?? 0,
  };
  return Object.fromEntries(Object.entries(counts).filter(([, value]) => value > 0));
}

export function pageBySlug(slug: string): AdminPage | undefined {
  return ADMIN_PAGES.find((page) => page.slug === slug);
}

export function hrefOf(page: AdminPage): string {
  return page.slug ? `/admin/${page.slug}` : "/admin";
}
