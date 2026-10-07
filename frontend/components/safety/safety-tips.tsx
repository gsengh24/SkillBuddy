/**
 * First-chat safety tips (ARCHITECTURE.md §8, "Safety nudges"). Shown at the start of a
 * conversation, until it has a few messages.
 */
export function SafetyTips() {
  return (
    <div className="bg-green-tint border-green-line rounded-card flex flex-col gap-1.5 border px-4 py-3">
      <p className="text-mono-lg text-green font-mono uppercase">Staying safe</p>
      <ul className="text-meta-lg text-ink-2 flex list-disc flex-col gap-1 pl-5">
        <li>
          Keep chatting here until you&apos;re comfortable. You don&apos;t have to share your phone
          number or social accounts.
        </li>
        <li>Never send money or bank details, and be wary of anyone who asks.</li>
        <li>If you meet in person, meet somewhere public on campus.</li>
        <li>
          If something feels wrong, use <strong>Report</strong> under a message, or{" "}
          <strong>Block</strong> at the top of this chat.
        </li>
      </ul>
    </div>
  );
}
