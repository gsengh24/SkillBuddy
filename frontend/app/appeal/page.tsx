import type { Metadata } from "next";

import { AppealForm } from "@/components/auth/appeal-form";
import { Logo } from "@/components/ds/logo";

export const metadata: Metadata = { title: "Appeal", robots: { index: false } };

type Props = { searchParams: Promise<{ token?: string }> };

/** Where the suspension or ban email's appeal link lands (A3). No sign-in needed. */
export default async function AppealPage({ searchParams }: Props) {
  const { token = "" } = await searchParams;
  return (
    <main className="flex min-h-dvh items-center justify-center px-4 py-10">
      <div className="border-line bg-bg rounded-panel flex w-full max-w-md flex-col gap-4 border p-6">
        <Logo />
        <h1 className="font-display tracking-display text-[26px] leading-tight font-extrabold">
          Appeal a decision
        </h1>
        {token ? (
          <AppealForm token={token} />
        ) : (
          <p className="text-ink-2">This link isn&apos;t complete. Open it again from the email.</p>
        )}
      </div>
    </main>
  );
}
