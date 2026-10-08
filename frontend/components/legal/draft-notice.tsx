/** Shown on legal pages until a lawyer has reviewed them (ARCHITECTURE.md §8). */
export function DraftNotice() {
  return (
    <aside role="note" className="rounded-card border-line-strong bg-panel text-ink border p-4">
      <p className="text-title">Draft, pending legal review</p>
      <p className="text-meta-lg text-ink-2 mt-1">
        This page is a working draft written for development and testing. It has not been reviewed
        by a lawyer and is not yet a binding agreement. It will change before public launch.
      </p>
    </aside>
  );
}
