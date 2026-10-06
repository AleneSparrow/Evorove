import assert from "node:assert/strict";
import test from "node:test";
import { isValidBusinessId, slugifyBusinessId } from "./businessId.ts";

test("slugifies a business name the same way the engine does", () => {
  assert.equal(slugifyBusinessId("Ada's Plumbing Co"), "ada-s-plumbing-co");
  assert.equal(slugifyBusinessId("Evorove"), "evorove");
  assert.equal(slugifyBusinessId("  "), "business");
});

test("accepts only lowercase letters, numbers, and hyphens", () => {
  assert.equal(isValidBusinessId("evorove"), true);
  assert.equal(isValidBusinessId("ada-s-plumbing-co"), true);
  assert.equal(isValidBusinessId("Business"), false);
  assert.equal(isValidBusinessId(""), false);
});
