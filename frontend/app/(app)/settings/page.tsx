import { redirect } from "next/navigation";

/** /settings has no page of its own: settings live on You. */
export default function SettingsPage() {
  redirect("/you");
}
