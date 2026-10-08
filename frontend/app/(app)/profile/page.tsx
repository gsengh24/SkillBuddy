import { redirect } from "next/navigation";

type Props = { searchParams: Promise<{ welcome?: string }> };

/** The old "About you" page: now part of You (onboarding's step 2 keeps its flag). */
export default async function ProfilePage({ searchParams }: Props) {
  const { welcome } = await searchParams;
  redirect(welcome ? "/you?welcome=1" : "/you");
}
