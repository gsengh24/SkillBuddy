/** The event Home's inbox listens for (see `LiveRefresh`). */
export const HOME_CHANGED = "home:changed";

/** The event for a chat that was just marked read (see `ActivityList`). */
export const CHAT_READ = "home:chat-read";

/**
 * Something the Home inbox shows has changed (a request made, answered or closed, an intro
 * answered or sent), so the inbox should re-fetch its lists. Safe to call anywhere: nothing
 * happens where Home is not open.
 *
 * Home's lists load with its layout, which does not re-run when a person opens another item,
 * so whatever changes them has to say so.
 */
export function notifyHomeChanged(): void {
  window.dispatchEvent(new Event(HOME_CHANGED));
}

/**
 * A chat was just marked read. The inbox clears its unread dot on the spot, without
 * re-fetching anything: opening a chat that has new messages is common, and a full refresh
 * for one dot would cost more than opening the chat does.
 */
export function notifyChatRead(connectionId: string): void {
  window.dispatchEvent(new CustomEvent(CHAT_READ, { detail: connectionId }));
}
