import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { AccessDenied } from "@/components/admin/admin-shell";
import { TwoStepForm } from "@/components/admin/two-step-form";
import { Logo } from "@/components/ds/logo";
import { getTwoStepStatus } from "@/lib/admin/server";
import { ApiError } from "@/lib/api/errors";
import { getCurrentUser } from "@/lib/auth/session";

export const metadata: Metadata = { title: "Two-step login" };
export const dynamic = "force-dynamic";

/** The admin portal's second step: set it up the first time, then a code each time. */
export default async function TwoStepPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login?next=/admin");
  let enabled: boolean;
  try {
    enabled = (await getTwoStepStatus()).two_step_enabled;
  } catch (error) {
    if (error instanceof ApiError && error.status === 403) {
      return <AccessDenied reason="This part of the site is for the team that runs it." />;
    }
    throw error;
  }

  return (
    <main className="bg-panel flex min-h-dvh items-center justify-center px-4 py-10">
      <div className="border-line bg-bg rounded-panel flex w-full max-w-md flex-col gap-4 border p-6">
        <Logo />
        <h1 className="font-display tracking-display text-[26px] leading-tight font-extrabold">
          {enabled ? "Confirm it's you" : "Set up two-step login"}
        </h1>
        <TwoStepForm enabled={enabled} />
      </div>
    </main>
  );
}
