import { useEffect, useState } from "react";

// Finish the current revolution before closing the ring and drawing the check.
export function LoadingMark({
  busy,
  small = false,
  onComplete,
}: {
  busy: boolean;
  small?: boolean;
  onComplete?: () => void;
}) {
  const [phase, setPhase] = useState(busy ? "spinning" : "done");

  useEffect(() => {
    if (busy) setPhase("spinning");
    else if (matchMedia("(prefers-reduced-motion: reduce)").matches)
      setPhase((current) => (current === "spinning" ? "filling" : current));
  }, [busy]);

  return (
    <span
      className={`loading-mark ${small ? "loading-mark-small" : ""}`}
      data-phase={phase}
      aria-hidden="true"
    >
      <svg
        className="mark-ring"
        viewBox="0 0 64 64"
        onAnimationIteration={() => {
          if (!busy) setPhase("filling");
        }}
        onAnimationEnd={(event) => {
          if (event.animationName === "spin" && !busy) setPhase("filling");
          if (event.animationName === "finish-ring") setPhase("drawing");
        }}
      >
        <circle className="mark-track" cx="32" cy="32" r="28" />
        <circle className="mark-arc" cx="32" cy="32" r="28" />
      </svg>
      {!small && <span className="loader-center">f</span>}
      <svg className="mark-check" viewBox="0 0 64 64">
        <path
          d={small ? "M14 32 26 44 50 20" : "M20 32 28 40 44 24"}
          pathLength="1"
          onAnimationEnd={(event) => {
            if (event.animationName !== "finish-check") return;
            setPhase("done");
            onComplete?.();
          }}
        />
      </svg>
    </span>
  );
}
