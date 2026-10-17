import { useId } from "react";
export function DemoScene({ time = 0 }: { time?: number }) {
  const id = useId();
  return (
    <svg
      className="demo-scene"
      viewBox="0 0 900 470"
      role="img"
      aria-label="Иллюстрация кассовой зоны, демонстрационный пример"
    >
      <defs>
        <pattern
          id={id}
          width="75"
          height="75"
          patternUnits="userSpaceOnUse"
          patternTransform="skewX(-12)"
        >
          <rect width="75" height="75" fill="#c2c8c5" />
          <path d="M75 0H0V75" fill="none" stroke="#aeb8b3" />
        </pattern>
      </defs>
      <rect width="900" height="470" fill={`url(#${id})`} />
      <path d="M0 0h900v60L0 98z" fill="#d9dfd9" />
      <path d="M0 98 900 60" stroke="#eff1ec" strokeWidth="8" />
      <path d="m50 130 175-15 10 230-175 17z" fill="#8f9c94" />
      <path d="m64 142 146-12 8 194-146 15z" fill="#aab6ae" />
      <path d="m275 88 410-25 72 335-420 31z" fill="#8b9489" opacity=".35" />
      <path d="m262 76 410-25 72 335-420 31z" fill="#dcd8cf" />
      <path d="m279 94 378-23 5 29-377 26z" fill="#a5ada6" />
      <path d="m440 80 15 317" stroke="#899d96" strokeWidth="6" opacity=".7" />
      <path
        d="m445 81 208-12 51 296-244 19z"
        fill="#c8e2dc"
        fillOpacity=".17"
        stroke="#f5ffff"
        strokeWidth="3"
      />
      <g transform="translate(320 145) rotate(-4)">
        <rect width="97" height="65" rx="5" fill="#3e4946" />
        <rect x="6" y="6" width="85" height="51" rx="2" fill="#637d76" />
        <path d="M48 65v23m-20 0h42" stroke="#4c5752" strokeWidth="8" />
        <rect x="8" y="98" width="88" height="30" rx="3" fill="#9ba39c" />
        <path
          d="M18 106h66m-66 7h66m-60 7h54"
          stroke="#76827b"
          strokeWidth="3"
        />
      </g>
      <g transform="translate(525 186) rotate(-5)">
        <rect width="98" height="70" rx="6" fill="#6f7973" />
        <rect x="8" y="9" width="82" height="30" rx="3" fill="#343f3a" />
        <rect x="12" y="47" width="74" height="14" rx="2" fill="#a3ada4" />
      </g>
      <g transform="translate(495 296) rotate(-5)">
        <rect width="62" height="37" rx="2" fill="#e0e4ce" />
        <path
          d="M7 8h46M7 15h46M7 22h46M7 29h46"
          stroke="#a4b194"
          strokeWidth="2"
        />
        <rect x="27" width="9" height="37" fill="#c6b6b0" />
      </g>
      <g transform="translate(240 245)">
        <ellipse cy="95" rx="47" ry="27" fill="#5e6a63" opacity=".2" />
        <path d="M-32 20q32-22 64 0l12 57q-44 25-88 0z" fill="#58616b" />
        <path
          d="m-25 27 41-8 35-22"
          stroke="#68717a"
          strokeWidth="20"
          strokeLinecap="round"
        />
        <ellipse cy="-1" rx="21" ry="24" fill="#bca58b" />
        <path d="M-21-3q-3-30 25-25 23 1 17 26z" fill="#40423f" />
      </g>
      <g transform={`translate(${time > 40 ? 689 : 727} 253)`}>
        <ellipse cy="104" rx="45" ry="25" fill="#5e6a63" opacity=".2" />
        <path d="M-30 24q30-19 60 0l11 59q-42 23-82 0z" fill="#8b7669" />
        <path
          d="m-25 33-30-17-35 16"
          stroke="#998172"
          strokeWidth="20"
          strokeLinecap="round"
        />
        <ellipse cy="0" rx="21" ry="25" fill="#c6ac91" />
        <path d="M-22-3q0-31 25-25 22 2 19 28l-10-12-25 1z" fill="#555048" />
      </g>
      {time > 40 && (
        <g>
          <rect
            x="480"
            y="278"
            width="98"
            height="72"
            rx="5"
            fill="none"
            stroke="#e9b967"
            strokeWidth="2"
            strokeDasharray="7 4"
          />
          <rect x="480" y="250" width="98" height="20" rx="3" fill="#e9b967" />
          <text
            x="529"
            y="264"
            textAnchor="middle"
            fill="#463c2a"
            fontSize="10"
            fontFamily="monospace"
          >
            СОБЫТИЕ {time > 70 ? "02" : "01"}
          </text>
        </g>
      )}
      <rect width="900" height="470" fill="#18382d" opacity=".1" />
      <text
        x="28"
        y="35"
        fill="#f4f5ed"
        fontSize="13"
        letterSpacing="2"
        fontFamily="monospace"
      >
        КАМЕРА 01 / КАССОВАЯ ЗОНА
      </text>
      <circle cx="30" cy="437" r="4" fill="#efc7b9" />
      <text x="44" y="442" fill="#fff" fontSize="12" fontFamily="monospace">
        ДЕМО · ИЛЛЮСТРАЦИЯ
      </text>
    </svg>
  );
}
