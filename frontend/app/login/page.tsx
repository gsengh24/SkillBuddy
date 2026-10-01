import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { LoginForm } from "@/components/auth/login-form";
import { safeNextPath } from "@/lib/auth/redirect";
import { getCurrentUser } from "@/lib/auth/session";
import { brand } from "@/lib/brand";

export const metadata: Metadata = { title: "Sign in" };
export const dynamic = "force-dynamic";

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string | string[] }>;
}) {
  const { next } = await searchParams;
  const nextPath = safeNextPath(typeof next === "string" ? next : undefined);
  // Already signed in: skip the form. If the API is unreachable, show the form anyway.
  const user = await getCurrentUser().catch(() => null);
  if (user) redirect(nextPath);

  return (
    <main className="mx-auto flex min-h-dvh max-w-3xl flex-col items-center justify-center gap-8 px-6 py-16">
      <LoginForm nextPath={nextPath} />
      <Link href="/" className="text-sm text-slate-600 underline">
        Back to {brand.name}
      </Link>
    </main>
  );
}
