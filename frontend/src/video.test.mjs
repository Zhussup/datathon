import assert from "node:assert/strict";
import { test } from "node:test";
import { validateVideo, formatTime, demoTimestamp } from "./video.ts";

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

test("formats video duration", () => {
  assert.equal(formatTime(0), "00:00");
  assert.equal(formatTime(78.9), "01:18");
  assert.equal(formatTime(105), "01:45");
});

test("demo timestamps stay within the actual recording", () => {
  for (const duration of [0.01, 5, 300]) {
    assert.ok(
      demoTimestamp(duration) >= 0 && demoTimestamp(duration) < duration,
    );
  }
  for (const duration of [0, -1, NaN, Infinity])
    assert.equal(demoTimestamp(duration), 0);
  assert.equal(demoTimestamp(100, 0.18), 18);
  assert.equal(demoTimestamp(100, -1), 0);
  assert.ok(demoTimestamp(100, 2) < 100);
  assert.equal(demoTimestamp(100, NaN), 0);
});
