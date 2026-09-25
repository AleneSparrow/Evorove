import type { ProcessState } from "../api/client";

/** Owner CRM tabs from FOUNDATION.md. Mapped from ProcessState only — not SalesStage. */
/** Four owner tabs from FOUNDATION.md. Lost is kept so closed-without-sale leads do not vanish. */
export const CRM_BOARD_TABS = ["cold", "in_progress", "offer_made", "done"] as const;
export const CRM_TABS = ["cold", "in_progress", "offer_made", "done", "lost"] as const;
export type CrmTab = (typeof CRM_TABS)[number];

export const CRM_TAB_META: Record<CrmTab, { label: string; hint: string }> = {
  cold: { label: "Cold", hint: "Found. Not written yet." },
  in_progress: { label: "In progress", hint: "The engine is talking." },
  offer_made: { label: "Offer made", hint: "Value named. Not closed." },
  done: { label: "Done", hint: "Sale happened or the hour is set." },
  lost: { label: "Lost", hint: "This thread ended without a sale." },
};

export function mapCrmTab(state: ProcessState): CrmTab {
  switch (state) {
    case "NEW_LEAD":
      return "cold";
    case "QUALIFIED":
    case "QUOTED":
      return "offer_made";
    case "BOOKED":
    case "WON":
    case "PAID":
    case "COMPLETED":
    case "REVIEW_REQUESTED":
      return "done";
    case "LOST":
    case "CANCELLED":
      return "lost";
    default:
      return "in_progress";
  }
}

export type EngagementBand = "high" | "medium" | "low";

export function engagementBand(eventCount: number, updatedAtIso: string, now = Date.now()): EngagementBand {
  const ageHours = Math.max(0, (now - new Date(updatedAtIso).getTime()) / 36e5);
  if (eventCount >= 6 || (eventCount >= 2 && ageHours < 24)) return "high";
  if (eventCount >= 3 || ageHours < 72) return "medium";
  return "low";
}

export const ENGAGEMENT_LABEL: Record<EngagementBand, string> = {
  high: "High",
  medium: "Medium",
  low: "Low",
};
