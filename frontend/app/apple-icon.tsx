import { ImageResponse } from "next/og";

import { colors } from "@/lib/design/tokens";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

/** The home-screen icon: the placeholder four-dot mark (see components/ds/logo.tsx). */
export default function AppleIcon() {
  const dot = (fill: string) => ({ width: 52, height: 52, borderRadius: 26, background: fill });
  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: colors.bg,
      }}
    >
      <div style={{ display: "flex", flexWrap: "wrap", width: 124, gap: 20 }}>
        <div style={dot(colors.green)} />
        <div style={dot(colors.ink)} />
        <div style={dot(colors.ink)} />
        <div style={dot(colors.green)} />
      </div>
    </div>,
    size,
  );
}
