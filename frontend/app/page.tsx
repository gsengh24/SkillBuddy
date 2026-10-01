import Link from "next/link";
import { Suspense } from "react";

import { ApiStatusFallback, ApiStatusIndicator } from "@/components/api-status";
import { brand } from "@/lib/brand";

// The status indicator reflects the API right now, so never serve a cached render.
export const dynamic = "force-dynamic";

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-3xl flex-col justify-center gap-10 px-6 py-16">
      <header className="flex flex-col gap-4">
        <p className="text-sm font-semibold tracking-wide text-indigo-600 uppercase">
          {brand.name}
        </p>
        <h1 className="text-4xl font-bold tracking-tight text-balance text-slate-900 sm:text-5xl">
          {brand.tagline}
        </h1>
        <p className="max-w-2xl text-lg text-pretty text-slate-600">{brand.description}</p>
        <div>
          <Link
            href="/login"
            className="inline-block rounded-md bg-indigo-600 px-5 py-2.5 font-semibold text-white hover:bg-indigo-700"
          >
            Sign in or create an account
          </Link>
        </div>
      </header>

      <section aria-label="System status">
        <Suspense fallback={<ApiStatusFallback />}>
          <ApiStatusIndicator />
        </Suspense>
      </section>
    </main>
  );
}
