import assert from "node:assert/strict";
import { test } from "node:test";
import { validateVideo, formatTime, findings } from "./demo.ts";

test("video validation enforces supported formats and size boundaries", () => {
  assert.equal(
    validateVideo({ name: "cashdesk.MOV", size: 29 * 1024 * 1024 }),
    "",
  );
  assert.equal(
    validateVideo({ name: "cashdesk.mp4", size: 200 * 1024 * 1024 }),
    "",
  );
  assert.match(validateVideo({ name: "video.mov.exe", size: 100 }), /формате/);
  assert.match(validateVideo({ name: "video.mov", size: 0 }), /пуст/);
  assert.match(
    validateVideo({ name: "video.mov", size: 200 * 1024 * 1024 + 1 }),
    /200 МБ/,
  );
});

test("event timestamps match the player timeline", () => {
  assert.equal(formatTime(0), "00:00");
  assert.equal(formatTime(78.9), "01:18");
  assert.equal(formatTime(105), "01:45");
  assert.equal(new Set(findings.map((f) => f.id)).size, findings.length);
  assert.ok(findings.every((f) => f.time >= 0 && f.time <= 105));
});
