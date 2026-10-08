/** How someone heard of the service, when they apply to join (A5). The API's fixed list. */
export const APPLICATION_SOURCES = [
  { value: "friend", label: "A friend" },
  { value: "college", label: "My college" },
  { value: "social_media", label: "Social media" },
  { value: "search", label: "A web search" },
  { value: "event", label: "An event" },
  { value: "other", label: "Somewhere else" },
] as const;

export function sourceLabel(source: string): string {
  return APPLICATION_SOURCES.find((item) => item.value === source)?.label ?? source;
}
