import { redirect } from "next/navigation";

/** Pair spaces used to live here; they are now the groups at /teams (ADR 0018). */
export default function SpacesPage(): never {
  redirect("/teams");
}
