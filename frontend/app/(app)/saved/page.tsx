import { redirect } from "next/navigation";

/** Saving people isn't built yet, so there is no Saved tab; old links land on Home. */
export default function SavedPage() {
  redirect("/home");
}
