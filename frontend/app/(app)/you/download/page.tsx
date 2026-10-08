import type { Metadata } from "next";

import { buttonClasses } from "@/components/ds/button";
import { TextLink } from "@/components/ui/text-link";
import { getCurrentUser } from "@/lib/auth/session";
import { redirect } from "next/navigation";

export const metadata: Metadata = { title: "Download your data", robots: { index: false } };
export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<{ export?: string; token?: string }> };

const ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const TOKEN = /^[A-Za-z0-9_-]{20,128}$/;

/**
 * Where the "Download my data" email lands. The file needs both the session and the
 * emailed token; the API checks both, so this page only offers the link.
 */
export default async function DownloadPage({ searchParams }: Props) {
  const { export: id = "", token = "" } = await searchParams;
  const user = await getCurrentUser();
  if (!user) {
    const back = `/you/download?${new URLSearchParams({ export: id, token })}`;
    redirect(`/login?next=${encodeURIComponent(back)}`);
  }
  const valid = ID.test(id) && TOKEN.test(token);

  return (
    <div className="flex max-w-2xl flex-col gap-4">
      <h1 className="text-headline lg:text-headline-lg">Download your data</h1>
      {valid ? (
        <>
          <p className="text-ink-2">
            Your file has your account, profile, requests, intros, connections and messages, as
            JSON. The link from the email works for a limited time and only for your account.
          </p>
          <a
            href={`/api/v1/me/data-exports/${id}/download?${new URLSearchParams({ token })}`}
            download
            className={buttonClasses({ variant: "primary" }, "self-start")}
          >
            Download the file
          </a>
        </>
      ) : (
        <p className="text-ink-2">
          This link isn&apos;t complete. Open it again from the email, or ask for a new one on your
          profile.
        </p>
      )}
      <p>
        <TextLink href="/you#s-data">Back to your profile</TextLink>
      </p>
    </div>
  );
}
