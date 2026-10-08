import { redirect } from "next/navigation";

/** The old Account settings page: now the account sections of You. */
export default function AccountSettingsPage() {
  redirect("/you#s-security");
}
