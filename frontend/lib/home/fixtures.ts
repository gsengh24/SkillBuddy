import type { Connection, Intro, MatchRequest, Person } from "@/lib/api/schemas";

/** Synthetic data for Home's tests. No real people. */

export const NOW = new Date("2026-10-08T12:00:00Z");

export function minutesAgo(minutes: number): string {
  return new Date(NOW.getTime() - minutes * 60_000).toISOString();
}

export function person(overrides: Partial<Person> = {}): Person {
  return {
    user_id: "22222222-0000-4000-8000-000000000002",
    display_name: null,
    links: null,
    summary: "Designs mobile apps.",
    offers: ["Figma"],
    seeks: [],
    interests: [],
    availability: "weekends",
    languages: ["English"],
    ...overrides,
  };
}

export function request(overrides: Partial<MatchRequest> = {}): MatchRequest {
  return {
    id: "req-1",
    text: "Budgeting app design",
    intent: null,
    requested_intent: null,
    status: "ready",
    match_count: 4,
    created_at: minutesAgo(30),
    matched_at: minutesAgo(2),
    expires_at: minutesAgo(-60 * 24 * 30),
    ...overrides,
  } as MatchRequest;
}

export function intro(overrides: Partial<Intro> = {}): Intro {
  return {
    id: "intro-1",
    direction: "received",
    status: "pending",
    note: "Happy to help.",
    request_text: "React basics",
    reason: "You both build web apps.",
    person: person(),
    created_at: minutesAgo(60),
    expires_at: minutesAgo(-60 * 24 * 7),
    responded_at: null,
    ...overrides,
  };
}

export function connection(overrides: Partial<Connection> = {}): Connection {
  return {
    id: "conn-1",
    created_at: minutesAgo(60 * 24 * 3),
    person: person({ display_name: "Aarav R.", links: ["https://example.com/aarav"] }),
    unread_messages: 2,
    last_message_at: minutesAgo(12),
    ...overrides,
  } as Connection;
}
