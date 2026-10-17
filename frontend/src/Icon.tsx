import type { CSSProperties } from "react";
export type IconName =
  | "grid"
  | "upload"
  | "shield"
  | "arrow"
  | "play"
  | "check"
  | "clock"
  | "file"
  | "close"
  | "info"
  | "chevron"
  | "expand"
  | "eye"
  | "pause"
  | "film";
const paths: Record<IconName, string> = {
  grid: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
  upload: "M12 16V3 m-5 5 5-5 5 5 M4 16v5h16v-5",
  shield: "M12 3 3 7v5c0 5 9 9 9 9s9-4 9-9V7z m-4 9 3 3 5-6",
  arrow: "M4 12h16 m-6-6 6 6-6 6",
  play: "m9 5 11 7-11 7z",
  pause: "M8 5v14 M16 5v14",
  check: "m5 12 4 4L19 6",
  clock: "M12 8v5l3 2 M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18",
  file: "M14 2H5v20h14V7z m0-5v5h5 M8 12h8 M8 16h5",
  close: "m6 6 12 12 M6 18 18 6",
  info: "M12 11v6 M12 7v.1 M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20",
  chevron: "m9 5 7 7-7 7",
  expand: "M8 3H3v5 M16 3h5v5 M3 16v5h5 M21 16v5h-5",
  eye: "M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12 M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6",
  film: "M3 3h18v18H3z M7 3v18 M17 3v18 M3 8h4 M3 16h4 M17 8h4 M17 16h4",
};
export function Icon({
  name,
  size = 20,
  style,
}: {
  name: IconName;
  size?: number;
  style?: CSSProperties;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.65"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      style={style}
    >
      <path d={paths[name]} />
    </svg>
  );
}
