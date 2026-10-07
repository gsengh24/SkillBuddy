"use client";

import { useSyncExternalStore } from "react";

/** "Good morning", "Good afternoon" or "Good evening" by the hour on this device. */
export function greetingFor(hour: number): string {
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

const subscribe = () => () => undefined;

/**
 * The greeting label. The server (on UTC) and the first paint say "Hello"; after load the
 * browser switches to the greeting for its own clock, so it is never wrong for the reader.
 */
export function Greeting({ className }: { className?: string }) {
  const text = useSyncExternalStore(
    subscribe,
    () => greetingFor(new Date().getHours()),
    () => "Hello",
  );
  return <p className={className}>{text}</p>;
}
