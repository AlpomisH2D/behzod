import React from "react";
import { Easing, interpolate } from "remotion";
import {
  Band,
  BrickPhone,
  C,
  Sfx,
  Stage,
  Stamp,
  Tag,
  easeBack,
  p,
  rnd,
  useSec,
} from "./common";
import { DUR } from "./timing";

const center: React.CSSProperties = {
  position: "absolute",
  left: 0,
  right: 0,
  display: "flex",
  justifyContent: "center",
};

/* ---------- 6 · Konveyer: etik, shina, kabel, TV ---------- */
const Boot = () => (
  <svg width="260" height="300" viewBox="0 0 260 300">
    <path d="M60 10 H150 V170 C150 200 250 190 250 250 V290 H20 V10 Z" fill="#2f7a4a" stroke="#14233F" strokeWidth="8" strokeLinejoin="round" />
    <rect x="20" y="260" width="230" height="30" fill="#14233F" />
    <rect x="60" y="10" width="90" height="26" fill="#3fa163" />
  </svg>
);
const Tire = () => (
  <svg width="280" height="280" viewBox="0 0 280 280">
    <circle cx="140" cy="140" r="130" fill="#1b1b22" stroke="#444" strokeWidth="6" />
    <circle cx="140" cy="140" r="62" fill="#9aa3b5" />
    <circle cx="140" cy="140" r="20" fill="#1b1b22" />
    {Array.from({ length: 16 }).map((_, i) => (
      <rect key={i} x="134" y="8" width="12" height="26" fill="#444" transform={`rotate(${i * 22.5} 140 140)`} />
    ))}
  </svg>
);
const Cable = () => (
  <svg width="280" height="280" viewBox="0 0 280 280">
    <circle cx="140" cy="140" r="125" fill="#d9702b" />
    <circle cx="140" cy="140" r="80" fill="none" stroke="#14233F" strokeWidth="10" />
    <circle cx="140" cy="140" r="55" fill="none" stroke="#14233F" strokeWidth="10" />
    <circle cx="140" cy="140" r="26" fill="#14233F" />
  </svg>
);
const TV = () => (
  <svg width="320" height="280" viewBox="0 0 320 280">
    <rect x="10" y="30" width="300" height="220" rx="26" fill="#6b4a2a" />
    <rect x="34" y="52" width="210" height="176" rx="22" fill="#9bd1c4" />
    <circle cx="276" cy="90" r="14" fill="#d9c9a3" />
    <circle cx="276" cy="140" r="14" fill="#d9c9a3" />
    <path d="M110 30 L70 0 M200 30 L240 0" stroke="#14233F" strokeWidth="8" strokeLinecap="round" />
  </svg>
);

export const Scene6: React.FC = () => {
  const t = useSec();
  const items = [
    { C: Boot, label: "Etik", at: 0.6 },
    { C: Tire, label: "Shina", at: 1.9 },
    { C: Cable, label: "Kabel", at: 3.2 },
    { C: TV, label: "TV", at: 4.5 },
  ];
  return (
    <Stage dur={DUR[5]}>
      <Sfx at={0} src="whoosh" volume={0.5} />
      {items.map((it) => (
        <Sfx key={it.label} at={it.at + 0.45} src="stamp" volume={0.45} />
      ))}
      {[0.2, 0.7, 1.2, 1.7, 2.2, 2.7, 3.2, 3.7, 4.2, 4.7, 5.2, 5.7].map((a) => (
        <Sfx key={a} at={a} src="tick" volume={0.25} />
      ))}
      <Sfx at={6.2} src="ding" volume={0.4} />
      {/* konveyer */}
      <div style={{ position: "absolute", left: 0, right: 0, top: 1030, height: 60, background: "#2b3652" }} />
      <svg width="1080" height="40" style={{ position: "absolute", top: 1090 }}>
        {Array.from({ length: 24 }).map((_, i) => (
          <rect key={i} x={((i * 60 + t * 220) % 1440) - 180} y="0" width="30" height="30" rx="6" fill="#47557a" />
        ))}
      </svg>
      {items.map(({ C: Comp, label, at }) => {
        const x = interpolate(t, [at, at + 1.3], [1250, -500], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
        const inView = t >= at && t <= at + 1.3;
        const labelK = p(t, at + 0.45, 0.35, easeBack);
        return (
          <React.Fragment key={label}>
            <div style={{ position: "absolute", left: 0, top: 740, translate: `${x}px ${Math.sin(t * 14 + at) * 3}px`, opacity: inView ? 1 : 0 }}>
              <Comp />
            </div>
            {t > at + 0.4 && t < at + 1.6 ? (
              <div style={{ ...center, top: 1210, scale: String(labelK) }}>
                <Tag size={78}>{label}</Tag>
              </div>
            ) : null}
          </React.Fragment>
        );
      })}
      {t > 5.9 ? (
        <div style={{ ...center, top: 560, scale: String(p(t, 5.9, 0.5, easeBack)) }}>
          <Band size={90} color={C.orange} rotate={-3}>va yana ko&apos;p...</Band>
        </div>
      ) : null}
    </Stage>
  );
};

/* ---------- 7 · Xelsinki → Moskva, 800 g ---------- */
export const Scene7: React.FC = () => {
  const t = useSec();
  const line = p(t, 0.6, 3.2, Easing.inOut(Easing.cubic));
  const ax = 220, ay = 560, bx = 840, by = 1200;
  const px = ax + (bx - ax) * line;
  const py = ay + (by - ay) * line - Math.sin(line * Math.PI) * 120;
  const arrive = t > 3.8;
  return (
    <Stage dur={DUR[6]}>
      <Sfx at={0.1} src="whoosh" volume={0.5} />
      <Sfx at={0.6} src="click" />
      <Sfx at={1.0} src="blip" volume={0.4} />
      <Sfx at={2.0} src="blip" volume={0.4} />
      <Sfx at={3.8} src="ding" />
      <Sfx at={3.85} src="ding" volume={0.5} />
      <Sfx at={5.6} src="stamp" volume={0.5} />
      <svg width="1080" height="1920" style={{ position: "absolute", inset: 0 }}>
        {[0, 1, 2, 3, 4, 5, 6, 7, 8].map((i) => (
          <line key={`h${i}`} x1="0" x2="1080" y1={300 + i * 170} y2={300 + i * 170} stroke={C.cream} strokeOpacity="0.08" strokeWidth="3" />
        ))}
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <line key={`v${i}`} y1="300" y2="1700" x1={i * 216} x2={i * 216} stroke={C.cream} strokeOpacity="0.08" strokeWidth="3" />
        ))}
        <path
          d={`M${ax} ${ay} Q${(ax + bx) / 2 - 120} ${(ay + by) / 2 - 220} ${bx} ${by}`}
          fill="none" stroke={C.orange} strokeWidth="8" strokeDasharray="22 16" strokeLinecap="round"
          pathLength={1}
          style={{ strokeDasharray: "0.02 0.014", strokeDashoffset: 1 - line }}
          opacity={line > 0 ? 1 : 0}
        />
        <circle cx={ax} cy={ay} r="18" fill={C.cream} />
        <circle cx={bx} cy={by} r="18" fill={C.cream} />
        {arrive
          ? [0, 1, 2].map((i) => {
              const k = ((t - 3.8) * 0.9 + i / 3) % 1;
              return <circle key={i} cx={bx} cy={by} r={20 + k * 150} fill="none" stroke={C.orange} strokeWidth="6" opacity={1 - k} />;
            })
          : null}
        <text x={ax - 30} y={ay - 50} fill={C.cream} fontSize="56" fontWeight="900" letterSpacing="3">XELSINKI</text>
        <text x={bx - 270} y={by + 90} fill={C.cream} fontSize="56" fontWeight="900" letterSpacing="3">MOSKVA</text>
      </svg>
      <div style={{ position: "absolute", left: px - 85, top: py - 160, scale: "0.5", transformOrigin: "top left", rotate: `${interpolate(line, [0, 1], [-14, 14])}deg`, opacity: p(t, 0.5, 0.3) }}>
        <BrickPhone antenna screen="#a6e1a0" />
      </div>
      <div style={{ position: "absolute", left: 80, top: 1470, scale: String(p(t, 1.8, 0.5, easeBack)) }}>
        <Tag size={96} color={C.orange}>800 g</Tag>
      </div>
      <div style={{ position: "absolute", left: 120, top: 1160, opacity: p(t, 5.3, 0.4) }}>
        <Stamp at={5.5} size={70} rotate={-8}>1987</Stamp>
      </div>
    </Stage>
  );
};

/* ---------- 8 · Dunyo xaritasi va 40% ---------- */
const BLOBS = [
  // [cx, cy, rx, ry] — qit'alar taxminiy ellipslar (0..100 koordinata)
  [24, 32, 14, 16], [30, 56, 7, 17], [52, 28, 8, 10], [54, 52, 8, 16],
  [72, 30, 18, 12], [82, 62, 6, 5], [14, 20, 5, 6],
];

export const Scene8: React.FC = () => {
  const t = useSec();
  const dots: { x: number; y: number; r: number }[] = [];
  for (let gy = 0; gy < 42; gy++) {
    for (let gx = 0; gx < 36; gx++) {
      const nx = (gx / 36) * 100;
      const ny = (gy / 42) * 80;
      if (BLOBS.some(([cx, cy, rx, ry]) => ((nx - cx) / rx) ** 2 + ((ny - cy) / ry) ** 2 < 1)) {
        dots.push({ x: gx, y: gy, r: rnd(gx * 91 + gy * 7) });
      }
    }
  }
  const bar = p(t, 1.8, 2.4, Easing.out(Easing.cubic));
  return (
    <Stage dur={DUR[7]}>
      <Sfx at={0} src="whoosh" volume={0.5} />
      <Sfx at={0.4} src="riser" volume={0.35} />
      <Sfx at={1.8} src="tick" volume={0.5} />
      <Sfx at={2.6} src="tick" volume={0.5} />
      <Sfx at={3.4} src="tick" volume={0.5} />
      <Sfx at={4.3} src="ding" />
      <svg width="1080" height="720" viewBox="0 0 36 42" style={{ position: "absolute", left: 0, top: 220 }} preserveAspectRatio="xMidYMid meet">
        {dots.map((d, i) => {
          const on = p(t, 0.3 + d.r * 2.6, 0.3);
          return <circle key={i} cx={d.x + 0.5} cy={d.y + 0.5} r={0.34} fill={on > 0.5 ? C.orange : C.cream} opacity={on > 0.5 ? 1 : 0.3} />;
        })}
      </svg>
      {/* diagramma */}
      <div style={{ position: "absolute", left: 160, top: 1000, width: 760, height: 520 }}>
        <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: 8, background: C.cream }} />
        {[12, 18, 24, 33, 40].map((v, i) => {
          const h = (v / 40) * 440 * Math.min(1, bar * 1.3 - i * 0.12 + 0.12 > 0 ? Math.max(0, Math.min(1, bar * 1.25 - i * 0.18)) : 0);
          return (
            <div key={i} style={{ position: "absolute", bottom: 8, left: 20 + i * 148, width: 108, height: h, background: i === 4 ? C.orange : C.cream, borderRadius: "10px 10px 0 0" }} />
          );
        })}
        <div style={{ position: "absolute", left: -40, bottom: 8 + 440, width: 840, height: 4, background: C.cream, opacity: 0.4 * bar }} />
      </div>
      <div style={{ ...center, top: 1560, scale: String(p(t, 4.0, 0.5, easeBack)) }}>
        <Tag size={74} color={C.orange}>2007 · ~40%</Tag>
      </div>
    </Stage>
  );
};

/* ---------- 9 · Qulash, sotildi ---------- */
export const Scene9: React.FC = () => {
  const t = useSec();
  const fall = p(t, 1.4, 0.9, Easing.in(Easing.cubic));
  const handoff = p(t, 2.6, 1.3, Easing.inOut(Easing.cubic));
  const stampHit = t > 4.6 && t < 4.8;
  return (
    <Stage dur={DUR[8]} shake={stampHit ? 14 : 0}>
      <Sfx at={0.1} src="whoosh" volume={0.5} />
      <Sfx at={0.4} src="riser" volume={0.4} />
      <Sfx at={1.9} src="boom" volume={0.9} />
      <Sfx at={2.7} src="whoosh" volume={0.6} />
      <Sfx at={4.6} src="stamp" volume={1} />
      <Sfx at={4.65} src="boom" volume={0.6} />
      {/* ustun diagramma */}
      <div style={{ position: "absolute", left: 340, top: 360, width: 400, height: 500 }}>
        {[0, 1, 2].map((i) => {
          const f = i === 2 ? fall : fall * 0.7;
          return (
            <div key={i} style={{ position: "absolute", bottom: 0, left: i * 140, width: 108, height: [300, 400, 500][i], background: i === 2 ? C.orange : C.cream, borderRadius: "10px 10px 0 0", transformOrigin: "bottom center", rotate: `${f * (i === 2 ? 74 : 20 + i * 8)}deg`, translate: `${f * 40}px ${f * 70}px`, opacity: 1 - f * 0.1 }} />
          );
        })}
      </div>
      {/* quti o'tkazish */}
      <div style={{ position: "absolute", left: 0, top: 1000, translate: `${interpolate(handoff, [0, 1], [-100, 480])}px 0`, rotate: `${Math.sin(handoff * Math.PI) * -6}deg`, opacity: p(t, 2.3, 0.3) }}>
        <div style={{ width: 260, height: 190, background: "#c9a26b", borderRadius: 10, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 900, fontSize: 62, color: C.ink, boxShadow: "0 10px 0 rgba(0,0,0,0.3)" }}>
          NOKIA
        </div>
      </div>
      {/* ikki qo'l (uslublashtirilgan) */}
      {[0, 1].map((i) => (
        <div key={i} style={{ position: "absolute", top: 1170, left: i === 0 ? -20 + handoff * 30 : 1080 - 330 - handoff * 30, width: 350, height: 56, borderRadius: 30, background: i === 0 ? C.cream : C.orange, opacity: p(t, 2.3, 0.3) }} />
      ))}
      <div style={{ ...center, top: 1320 }}>
        <Stamp at={4.6} size={150} rotate={-9}>SOTILDI</Stamp>
      </div>
      <div style={{ ...center, top: 1620, scale: String(p(t, 5.2, 0.5, easeBack)) }}>
        <Tag size={64}>2014 · Microsoft</Tag>
      </div>
    </Stage>
  );
};

/* ---------- 10 · Savol ---------- */
export const Scene10: React.FC = () => {
  const t = useSec();
  const pulse = 1 + Math.sin(t * 5) * 0.05;
  const text = "Birinchi telefoningiz?";
  const n = Math.floor(p(t, 1.0, 1.0, Easing.linear) * text.length);
  return (
    <Stage dur={DUR[9]}>
      <Sfx at={0.1} src="whoosh" volume={0.4} />
      <Sfx at={0.45} src="ding" volume={0.7} />
      {Array.from({ length: text.length }).map((_, i) => (
        <Sfx key={i} at={1.0 + (i / text.length) * 1.0} src="tick" volume={0.15} />
      ))}
      <div style={{ ...center, top: 420, scale: String(pulse * p(t, 0.2, 0.6, easeBack)) }}>
        <div style={{ fontSize: 760, fontWeight: 900, color: C.cream, lineHeight: 1, letterSpacing: -20 }}>?</div>
      </div>
      <div style={{ position: "absolute", left: 60, top: 1280, opacity: p(t, 0.6, 0.5) * 0.9 }}>
        <BrickPhone scale={0.28} />
      </div>
      <div style={{ ...center, top: 1400 }}>
        <Band size={72} color={C.cream} rotate={-1}>{text.slice(0, n) || " "}</Band>
      </div>
    </Stage>
  );
};
