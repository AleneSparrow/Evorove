/** Same slug as `business_id_from_name` in src/persistence/business_provisioning_service.py. */
const BUSINESS_ID_PATTERN = /^[a-z0-9][a-z0-9-]*$/;

export function slugifyBusinessId(name: string): string {
  const slug = name.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  return BUSINESS_ID_PATTERN.test(slug) ? slug : "business";
}

export function isValidBusinessId(value: string): boolean {
  return BUSINESS_ID_PATTERN.test(value);
}
