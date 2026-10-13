import React from "react";
import { Audio } from "@remotion/media";
import {
  AbsoluteFill,
  Easing,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export const C = {
  bg: "#14233F",
  bg2: "#1d3358",
  cream: "#F6F0E4",
  creamDark: "#E3D9C3",
  orange: "#D9702B",
  red: "#A4262C",
  ink: "#0C1730",
};

export const FONT = 'Inter, "Liberation Sans", Arial, sans-serif';

export const clampX = {
  extrapolateLeft: "clamp",
  extrapolateRight: "clamp",
} as const;

export const easeOut = Easing.bezier(0.16, 1, 0.3, 1);
export const easeBack = Easing.bezier(0.34, 1.56, 0.64, 1);

/** Sekundlarda vaqt. */
export const useSec = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return frame / fps;
};

/** 0..1 progress between two moments (seconds). */
export const p = (
  t: number,
  start: number,
  dur: number,
  easing: (n: number) => number = easeOut,
) => interpolate(t, [start, start + dur], [0, 1], { ...clampX, easing });

/** Deterministic pseudo-random 0..1. */
export const rnd = (n: number) => {
  const x = Math.sin(n * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x);
};

export const Sfx: React.FC<{
  at: number;
  src: string;
  volume?: number;
}> = ({ at, src, volume = 0.8 }) => {
  const { fps } = useVideoConfig();
  return (
    <Sequence from={Math.round(at * fps)} layout="none">
      <Audio src={staticFile(`sfx/${src}.wav`)} volume={volume} />
    </Sequence>
  );
};

/** Qog'oz donadorligi + vinyetka. Har 3 kadrda "qaynaydi" (qo'lda chizilgan hissi). */
export const Grain: React.FC = () => {
  const frame = useCurrentFrame();
  const seed = Math.floor(frame / 3) % 7;
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <svg width="100%" height="100%" style={{ opacity: 0.16, mixBlendMode: "overlay" }}>
        <filter id={`g${seed}`}>
          <feTurbulence
            type="fractalNoise"
            baseFrequency="0.85"
            numOctaves="2"
            seed={seed}
          />
          <feColorMatrix type="saturate" values="0" />
        </filter>
        <rect width="100%" height="100%" filter={`url(#g${seed})`} />
      </svg>
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(ellipse at center, rgba(0,0,0,0) 55%, rgba(0,0,0,0.45) 100%)",
        }}
      />
    </AbsoluteFill>
  );
};

/** Sahna foni: to'q ko'k + sekin kamera zoom + dag'al kamera siljishi. */
export const Stage: React.FC<{
  children: React.ReactNode;
  dur: number;
  shake?: number;
}> = ({ children, dur, shake = 0 }) => {
  const t = useSec();
  const zoom = interpolate(t, [0, dur], [1, 1.07], clampX);
  const sx = Math.sin(t * 60) * shake;
  const sy = Math.cos(t * 53) * shake;
  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(circle at 50% 40%, ${C.bg2}, ${C.bg} 70%)`,
        overflow: "hidden",
        fontFamily: FONT,
      }}
    >
      <AbsoluteFill
        style={{ scale: String(zoom), translate: `${sx}px ${sy}px` }}
      >
        {children}
      </AbsoluteFill>
      <Grain />
    </AbsoluteFill>
  );
};

/** Qog'oz bandi (krem yoki sariq) — qiyalik bilan. */
export const Band: React.FC<{
  children: React.ReactNode;
  color?: string;
  textColor?: string;
  size?: number;
  rotate?: number;
  style?: React.CSSProperties;
}> = ({
  children,
  color = C.cream,
  textColor = C.ink,
  size = 150,
  rotate = 0,
  style,
}) => (
  <div
    style={{
      display: "inline-block",
      background: color,
      color: textColor,
      fontWeight: 900,
      fontSize: size,
      letterSpacing: -4,
      lineHeight: 1,
      padding: `${size * 0.12}px ${size * 0.28}px`,
      rotate: `${rotate}deg`,
      boxShadow: "0 14px 0 rgba(0,0,0,0.28)",
      ...style,
    }}
  >
    {children}
  </div>
);

/** Kichik yorliq. */
export const Tag: React.FC<{
  children: React.ReactNode;
  color?: string;
  textColor?: string;
  size?: number;
  style?: React.CSSProperties;
}> = ({ children, color = C.cream, textColor = C.ink, size = 56, style }) => (
  <div
    style={{
      display: "inline-block",
      background: color,
      color: textColor,
      fontWeight: 800,
      fontSize: size,
      padding: `${size * 0.2}px ${size * 0.5}px`,
      borderRadius: 8,
      boxShadow: "0 8px 0 rgba(0,0,0,0.25)",
      ...style,
    }}
  >
    {children}
  </div>
);

/** Qizil muhr, zarb bilan uriladi. */
export const Stamp: React.FC<{
  at: number;
  children: React.ReactNode;
  size?: number;
  rotate?: number;
  style?: React.CSSProperties;
}> = ({ at, children, size = 120, rotate = -10, style }) => {
  const t = useSec();
  const k = p(t, at, 0.22, Easing.bezier(0.3, 0, 0.9, 0.5));
  const scale = interpolate(k, [0, 1], [3, 1]);
  const opacity = interpolate(t, [at, at + 0.08], [0, 1], clampX);
  return (
    <div
      style={{
        position: "absolute",
        scale: String(scale),
        opacity,
        rotate: `${rotate}deg`,
        border: `${size * 0.1}px solid ${C.red}`,
        color: C.red,
        fontWeight: 900,
        fontSize: size,
        padding: `${size * 0.05}px ${size * 0.3}px`,
        letterSpacing: 6,
        borderRadius: 14,
        mixBlendMode: "normal",
        ...style,
      }}
    >
      {children}
    </div>
  );
};

/** G'isht telefon (SVG-siz, divlardan). */
export const BrickPhone: React.FC<{
  scale?: number;
  antenna?: boolean;
  screen?: string;
}> = ({ scale = 1, antenna = false, screen = "#8fd08a" }) => (
  <div style={{ position: "relative", width: 340 * scale, height: 640 * scale }}>
    {antenna ? (
      <div
        style={{
          position: "absolute",
          left: 40 * scale,
          top: -90 * scale,
          width: 30 * scale,
          height: 120 * scale,
          background: "#222b3d",
          borderRadius: 14 * scale,
        }}
      />
    ) : null}
    <div
      style={{
        position: "absolute",
        inset: 0,
        background: "linear-gradient(160deg,#39465f,#1b2438)",
        borderRadius: 54 * scale,
        boxShadow: `0 ${16 * scale}px 0 rgba(0,0,0,0.35)`,
      }}
    />
    <div
      style={{
        position: "absolute",
        left: 44 * scale,
        top: 60 * scale,
        width: 252 * scale,
        height: 180 * scale,
        background: screen,
        borderRadius: 18 * scale,
        boxShadow: `inset 0 0 ${30 * scale}px rgba(0,60,0,0.35)`,
      }}
    />
    {Array.from({ length: 12 }).map((_, i) => (
      <div
        key={i}
        style={{
          position: "absolute",
          left: (52 + (i % 3) * 82) * scale,
          top: (290 + Math.floor(i / 3) * 80) * scale,
          width: 70 * scale,
          height: 56 * scale,
          background: "#5a6985",
          borderRadius: 26 * scale,
        }}
      />
    ))}
  </div>
);
