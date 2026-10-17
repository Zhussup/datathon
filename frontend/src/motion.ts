import { flushSync } from "react-dom";

const active = new Set<Animation>();
const targets = [
  ".status-panel, .upload-button",
  ".is-split .video-column",
  ".is-split .review-toolbar",
];

export function finishTransition() {
  for (const animation of active) animation.cancel();
  active.clear();
}

export function transition(update: () => void) {
  if (
    !document.documentElement?.animate ||
    matchMedia("(prefers-reduced-motion: reduce)").matches
  ) {
    finishTransition();
    update();
    return;
  }

  // Read the current on-screen positions before interrupting any running motion.
  const previous = targets.map((selector) => {
    const node = document.querySelector<HTMLElement>(selector);
    return node ? { node, rect: node.getBoundingClientRect() } : null;
  });
  finishTransition();
  document.documentElement.dataset.motion = "smooth";
  flushSync(update);

  let panelMoveDuration = 0;
  targets.forEach((selector, index) => {
    const node = document.querySelector<HTMLElement>(selector);
    if (!node) return;
    const rect = node.getBoundingClientRect();
    const from = previous[index];
    const sameNode = from?.node === node;
    const x = from
      ? sameNode
        ? from.rect.left - rect.left
        : from.rect.left + from.rect.width / 2 - rect.left - rect.width / 2
      : 0;
    const y = from
      ? sameNode
        ? from.rect.top - rect.top
        : from.rect.top + from.rect.height / 2 - rect.top - rect.height / 2
      : 14;
    const base = getComputedStyle(node).transform;
    const transform = base === "none" ? "" : base;
    const movingPanel =
      index === 0 && from?.node === node && Math.abs(x) + Math.abs(y) > 24;
    if (movingPanel) panelMoveDuration = 940;
    const animation = node.animate(
      [
        {
          transform: `translate(${x}px, ${y}px) ${transform}`,
          opacity: from?.node === node ? 1 : 0,
        },
        { transform: base, opacity: 1 },
      ],
      {
        duration: index === 0 ? (movingPanel ? 940 : 420) : 740,
        // Keep the preview hidden until the status has cleared its space.
        delay: !from && index > 0 ? panelMoveDuration + 80 : 0,
        fill: "backwards",
        easing: movingPanel
          ? "cubic-bezier(.4,0,.2,1)"
          : "cubic-bezier(.22,1,.36,1)",
      },
    );
    active.add(animation);
    void animation.finished
      .catch(() => {})
      .finally(() => active.delete(animation));
  });
}
