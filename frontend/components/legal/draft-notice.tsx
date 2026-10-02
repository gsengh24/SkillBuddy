/** Shown on legal pages until a lawyer has reviewed them (ARCHITECTURE.md §8). */
export function DraftNotice() {
  return (
    <aside
      role="note"
      className="rounded-card border-amber-edge bg-amber-tint text-amber-ink border p-4"
    >
      <p className="font-bold">Draft, pending legal review</p>
      <p className="text-small mt-1">
        This page is a working draft written for development and testing. It has not been reviewed
        by a lawyer and is not yet a binding agreement. It will change before public launch.
      </p>
    </aside>
  );
}
