import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const html = readFileSync(new URL("../../index.html", import.meta.url), "utf8");
const text = html
  .replace(/<script[\s\S]*?<\/script>/gi, " ")
  .replace(/<style[\s\S]*?<\/style>/gi, " ")
  .replace(/<[^>]+>/g, " ")
  .replace(/\s+/g, " ")
  .trim();

test("the static page carries the published offer before JavaScript runs", () => {
  assert.ok(text.length > 150);
  assert.match(text, /finds people in the open web/);
  assert.match(text, /\$199\/mo after trial — instead of a hire/);
  assert.match(text, /The United States today/);
  assert.doesNotMatch(text, /small business/i);
  assert.doesNotMatch(text, /salon/i);
  assert.doesNotMatch(text, /repair shop/i);
});
