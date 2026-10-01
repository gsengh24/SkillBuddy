/** Shown on legal pages until a lawyer has reviewed them (ARCHITECTURE.md §8). */
export function DraftNotice() {
  return (
    <aside
      role="note"
      className="rounded-lg border-2 border-amber-400 bg-amber-50 p-4 text-amber-900"
    >
      <p className="font-semibold">Draft, pending legal review</p>
      <p className="mt-1 text-sm">
        This page is a working draft written for development and testing. It has not been reviewed
        by a lawyer and is not yet a binding agreement. It will change before public launch.
      </p>
    </aside>
  );
}
