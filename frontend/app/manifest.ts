import type { MetadataRoute } from "next";

import { brand } from "@/lib/brand";
import { colors } from "@/lib/design/tokens";

/** The web app manifest: the product name and the placeholder mark. */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: brand.name,
    short_name: brand.name,
    description: brand.summary,
    start_url: "/home",
    display: "standalone",
    background_color: colors.bg,
    theme_color: colors.bg,
    icons: [
      { src: "/icon.svg", type: "image/svg+xml", sizes: "any" },
      { src: "/apple-icon", type: "image/png", sizes: "180x180" },
    ],
  };
}
