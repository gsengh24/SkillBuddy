import { ImageResponse } from "next/og";

import { brand } from "@/lib/brand";
import { colors } from "@/lib/design/tokens";

export const alt = `${brand.displayName}: say what you're building, meet who can help`;
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

/**
 * The Open Graph card, drawn from our own palette and words at build time: no photos, no
 * outside assets. The four-dot mark matches the placeholder logo.
 */
export default function OpenGraphImage() {
  const dot = (fill: string) => ({ width: 34, height: 34, borderRadius: 17, background: fill });
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        padding: 72,
        background: colors.greenTint,
        color: colors.ink,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
        <div style={{ display: "flex", flexWrap: "wrap", width: 80, gap: 12 }}>
          <div style={dot(colors.green)} />
          <div style={dot(colors.ink)} />
          <div style={dot(colors.ink)} />
          <div style={dot(colors.green)} />
        </div>
        <div style={{ fontSize: 56, fontWeight: 800, letterSpacing: "-0.04em" }}>
          {brand.wordmark}
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", fontSize: 76, fontWeight: 800 }}>
        <div style={{ letterSpacing: "-0.04em" }}>Say what you&apos;re building.</div>
        <div style={{ letterSpacing: "-0.04em", color: colors.green }}>Meet who can help.</div>
      </div>
    </div>,
    size,
  );
}
