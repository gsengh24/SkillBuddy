import { redirect } from "next/navigation";

/** The old free-text-first page, retired by step 5 (ADR 0022). Old links land on the steps. */
export default function DescribePage() {
  redirect("/onboarding");
}
