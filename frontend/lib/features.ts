import "server-only";

import { cache } from "react";

import { apiRequest } from "@/lib/api/client";
import { featuresSchema, type Features } from "@/lib/api/schemas";

/** Everything on, as when nothing is stored: used if the API can't be reached. */
const ALL_ON: Features = {
  features: {
    intro_requests: true,
    chats: true,
    ai_matching: true,
    pair_spaces: true,
    email_notifications: true,
  },
  message_max_length: 2000,
};

/** Which features are switched on (admin Settings page, A6). Cached per request. */
export const getFeatures = cache(async (): Promise<Features> => {
  try {
    return await apiRequest("/api/v1/features", featuresSchema);
  } catch {
    return ALL_ON;
  }
});
