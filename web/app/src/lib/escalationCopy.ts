export const ESCALATION_LABELS: Record<string, string> = {
  safety_emergency: "Safety or emergency language",
  urgent_request: "Customer requested urgent help",
  low_confidence: "Low confidence in the request",
  service_unclear: "Requested service was unclear",
  ai_review: "AI requested human review",
  service_area_uncertain: "Service area could not be confirmed",
  policy_review: "Business policy requires review",
  identity_conflict: "Contact details match another lead",
  already_pending: "Already waiting for review",
};

export const ESCALATION_ACTIONS: Record<string, string> = {
  safety_emergency: "Call or reply immediately — do not leave a safety issue on the board.",
  urgent_request: "The engine stopped. Confirm facts. Do not hop in to close a normal sale.",
  low_confidence: "Read the last message. Missing facts can be supplied without taking the sale.",
  service_unclear: "Confirm which service they need. The engine still owns the close.",
  ai_review: "Review the thread on CRM. Choose the next safe step, not a closer takeover.",
  service_area_uncertain: "Confirm location before the engine offers service.",
  policy_review: "Check this request against your business policy.",
  identity_conflict: "Verify the contact details before the engine continues.",
  already_pending: "A safety stop is already open on this case.",
};

export const ESCALATION_OUTCOMES: Record<string, string> = {
  already_pending: "No automatic next step until the safety stop is cleared.",
};

export const ESCALATION_FEEDBACK_LABELS: Record<string, string> = {
  unnecessary: "Staff marked the escalation unnecessary",
  missed: "Staff marked a missed escalation",
  wrong_service: "Wrong service was assumed",
  identity_same_customer: "Same customer, duplicate identity",
  identity_different_customer: "Different customer, identity conflict",
};

export const CONVERSATION_STATUS_LABELS: Record<string, string> = {
  ai_active: "Engine handling",
  human_takeover_requested: "Safety stop",
  human_takeover_active: "Risk reply in progress",
  closed: "Closed",
};
