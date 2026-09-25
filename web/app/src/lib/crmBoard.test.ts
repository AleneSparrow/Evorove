import assert from "node:assert/strict";
import test from "node:test";
import { CRM_BOARD_TABS, engagementBand, mapCrmTab } from "./crmBoard.ts";

test("owner board is four tabs; lost is mapped aside so it does not vanish", () => {
  assert.deepEqual([...CRM_BOARD_TABS], ["cold", "in_progress", "offer_made", "done"]);
});

test("maps process states onto the four CRM tabs plus lost", () => {
  assert.equal(mapCrmTab("NEW_LEAD"), "cold");
  assert.equal(mapCrmTab("QUALIFYING"), "in_progress");
  assert.equal(mapCrmTab("CONTACTED"), "in_progress");
  assert.equal(mapCrmTab("NEEDS_HUMAN"), "in_progress");
  assert.equal(mapCrmTab("QUALIFIED"), "offer_made");
  assert.equal(mapCrmTab("QUOTED"), "offer_made");
  assert.equal(mapCrmTab("BOOKED"), "done");
  assert.equal(mapCrmTab("COMPLETED"), "done");
  assert.equal(mapCrmTab("WON"), "done");
  assert.equal(mapCrmTab("LOST"), "lost");
});

test("engagement uses activity count and recency, not invented demographics", () => {
  const now = Date.parse("2026-09-12T12:00:00Z");
  assert.equal(engagementBand(8, "2026-09-01T12:00:00Z", now), "high");
  assert.equal(engagementBand(2, "2026-09-12T01:00:00Z", now), "high");
  assert.equal(engagementBand(1, "2026-08-01T12:00:00Z", now), "low");
});
