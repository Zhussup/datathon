import assert from "node:assert/strict";
import { test } from "node:test";
import { transition, finishTransition } from "./motion.ts";

test("updates stay synchronous and rapid changes cancel previous motion", async () => {
  const saved = {
    document: globalThis.document,
    matchMedia: globalThis.matchMedia,
    getComputedStyle: globalThis.getComputedStyle,
  };
  let updates = 0;
  let cancelled = 0;
  let animated = 0;
  try {
    globalThis.document = { documentElement: {} };
    globalThis.matchMedia = () => ({ matches: false });
    transition(() => updates++);
    assert.equal(updates, 1);

    const node = {
      getBoundingClientRect: () => ({
        left: 0,
        top: 0,
        width: 300,
        height: 200,
      }),
      animate: () => {
        animated++;
        return { finished: Promise.resolve(), cancel: () => cancelled++ };
      },
    };
    globalThis.document = {
      documentElement: { animate: () => {}, dataset: {} },
      querySelector: (selector) =>
        selector.startsWith(".status-panel") ? node : null,
    };
    globalThis.getComputedStyle = () => ({ transform: "none" });
    transition(() => updates++);
    transition(() => updates++);
    assert.equal(updates, 3);
    assert.equal(animated, 2);
    assert.equal(cancelled, 1);

    globalThis.matchMedia = () => ({ matches: true });
    transition(() => updates++);
    assert.equal(updates, 4);
    assert.equal(animated, 2);
    assert.equal(cancelled, 2);
    await Promise.resolve();
  } finally {
    finishTransition();
    Object.assign(globalThis, saved);
  }
});

test("preview stays hidden until the status panel finishes moving", async () => {
  const saved = {
    document: globalThis.document,
    matchMedia: globalThis.matchMedia,
    getComputedStyle: globalThis.getComputedStyle,
  };
  let split = false;
  const timings = {};
  const makeNode = (name) => ({
    getBoundingClientRect: () => ({
      left: name === "panel" && split ? 600 : 0,
      top: 0,
      width: 300,
      height: 200,
    }),
    animate: (frames, options) => {
      timings[name] = { frames, ...options };
      return { finished: Promise.resolve(), cancel() {} };
    },
  });
  const panel = makeNode("panel");
  const video = makeNode("video");
  try {
    globalThis.document = {
      documentElement: { animate() {}, dataset: {} },
      querySelector: (selector) =>
        selector.startsWith(".status-panel")
          ? panel
          : split && selector.includes("video-column")
            ? video
            : null,
    };
    globalThis.matchMedia = () => ({ matches: false });
    globalThis.getComputedStyle = () => ({ transform: "none" });
    transition(() => {
      split = true;
    });
    assert.ok(timings.video.delay >= timings.panel.duration);
    assert.equal(timings.video.frames[0].opacity, 0);
    assert.equal(timings.video.fill, "backwards");
    await Promise.resolve();
  } finally {
    finishTransition();
    Object.assign(globalThis, saved);
  }
});
