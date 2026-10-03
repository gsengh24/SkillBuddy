import { WhyBox } from "@/components/ui/why-box";

/**
 * First-chat safety tips (ARCHITECTURE.md §8, "Safety nudges"). Shown at the start of a
 * conversation, until it has a few messages.
 */
export function SafetyTips() {
  return (
    <WhyBox hue="amber" title="Staying safe">
      <ul className="flex list-disc flex-col gap-1 pl-5">
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
    </WhyBox>
  );
}
