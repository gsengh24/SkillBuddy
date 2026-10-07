import { redirect } from "next/navigation";

/**
 * Messages now live on Home, in one list with requests and intros (design spec 6.2). The
 * old list address goes there, with the Messages filter selected. Chats keep their own
 * address, /messages/[connectionId].
 */
export default function MessagesPage(): never {
  redirect("/home?filter=messages");
}
