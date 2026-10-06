import assert from "node:assert/strict";
import test from "node:test";
import { CRM_BOARD_TABS, CRM_TAB_META } from "../lib/crmBoard.ts";
import {
  BOARD_PREVIEW_DEFAULT_TAB,
  BOARD_PREVIEW_SCENES,
  BOARD_PREVIEW_TABS,
  boardPreviewCounts,
  flattenBoardPreviewCopy,
} from "../brand/boardPreview.ts";

test("landing board preview uses the four live CRM tabs", () => {
  assert.deepEqual([...BOARD_PREVIEW_TABS], [...CRM_BOARD_TABS]);
  assert.deepEqual(Object.keys(BOARD_PREVIEW_SCENES), [...CRM_BOARD_TABS]);
  assert.equal(BOARD_PREVIEW_DEFAULT_TAB, "in_progress");
  const counts = boardPreviewCounts();
  for (const tab of CRM_BOARD_TABS) {
    assert.equal(counts[tab], BOARD_PREVIEW_SCENES[tab].people.length);
    assert.ok(BOARD_PREVIEW_SCENES[tab].people.length >= 1);
    assert.equal(CRM_TAB_META[tab].hint.length > 0, true);
  }
});

test("cold preview has people and no conversation yet", () => {
  for (const person of BOARD_PREVIEW_SCENES.cold.people) {
    assert.equal(person.messages.length, 0);
    assert.match(person.summary, /Not written yet/);
  }
});

test("preview copy does not invent conversion rates, ticket ids, or discounts", () => {
  const copy = flattenBoardPreviewCopy();
  assert.doesNotMatch(copy, /\d+\s*%/);
  assert.doesNotMatch(copy, /\bCS-\d+/i);
  assert.doesNotMatch(copy, /\bdiscount\b/i);
  assert.match(BOARD_PREVIEW_SCENES.done.people[0].summary, /Paid on the business link/);
  assert.match(BOARD_PREVIEW_SCENES.offer_made.people[0].messages.at(-1)?.text ?? "", /\$199/);
});
