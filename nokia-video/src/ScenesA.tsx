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

/* ---------- 1 · Hook: telefon qog'ozga aylanadi ---------- */
export const Scene1: React.FC = () => {
  const t = useSec();
  const flip = p(t, 0.55, 0.3, Easing.inOut(Easing.quad));
  const phoneX = interpolate(flip, [0, 1], [1, 0]);
  const paperX = interpolate(flip, [0, 1], [0, 1]);
  const bounce = p(t, 0.85, 0.5, easeBack);
  return (
    <Stage dur={DUR[0]}>
      <Sfx at={0.5} src="whoosh" />
      <Sfx at={0.62} src="paper" volume={0.9} />
      <Sfx at={1.15} src="stamp" />
      <Sfx at={1.7} src="stamp" />
      <div style={{ ...center, top: 360 }}>
        <div style={{ position: "relative", width: 340, height: 640 }}>
          <div style={{ position: "absolute", scale: `${phoneX} 1`, rotate: `${flip * 8}deg` }}>
            <BrickPhone />
          </div>
          <div
            style={{
              position: "absolute",
              width: 340,
              height: 640,
              background: C.cream,
              scale: `${paperX} 1`,
              rotate: `${-6 + bounce * 0}deg`,
              boxShadow: "0 16px 0 rgba(0,0,0,0.3)",
              clipPath: "polygon(0 0, 82% 0, 100% 14%, 100% 100%, 0 100%)",
            }}
          >
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <div
                key={i}
                style={{
                  margin: "70px 36px 0",
                  height: 10,
                  background: C.creamDark,
                  width: `${60 + rnd(i) * 35}%`,
                }}
              />
            ))}
          </div>
        </div>
      </div>
      <div
        style={{
          ...center,
          top: 1050,
          translate: `${interpolate(p(t, 1.05, 0.35), [0, 1], [-900, 0])}px 0`,
        }}
      >
        <Band rotate={-4} size={170}>NOKIA</Band>
      </div>
      <div
        style={{
          ...center,
          top: 1260,
          translate: `${interpolate(p(t, 1.6, 0.35), [0, 1], [900, 0])}px 0`,
        }}
      >
        <Band rotate={3} size={92} color={C.orange} textColor={C.ink}>
          QOG&apos;OZMI?
        </Band>
      </div>
    </Stage>
  );
};

/* ---------- 2 · Arxiv papkasi, 1865, SIR muhri ---------- */
export const Scene2: React.FC = () => {
  const t = useSec();
  const drop = p(t, 0.15, 0.55, Easing.bounce);
  const open = p(t, 0.9, 0.5);
  const doc = p(t, 1.2, 0.7);
  return (
    <Stage dur={DUR[1]} shake={t > 2.4 && t < 2.6 ? 8 : 0}>
      <Sfx at={0.3} src="boom" volume={0.7} />
      <Sfx at={1.0} src="paper" />
      <Sfx at={1.3} src="whoosh" volume={0.5} />
      <Sfx at={2.45} src="stamp" volume={1} />
      <div style={{ ...center, top: 520, translate: `0 ${interpolate(drop, [0, 1], [-1000, 0])}px` }}>
        <div style={{ position: "relative", width: 760, height: 900 }}>
          {/* orqa panel */}
          <div style={{ position: "absolute", top: 40, left: 0, width: 760, height: 860, background: "#c9b88f", borderRadius: 12 }} />
          <div style={{ position: "absolute", top: 0, left: 0, width: 280, height: 70, background: "#c9b88f", borderRadius: "16px 16px 0 0" }} />
          {/* hujjat */}
          <div
            style={{
              position: "absolute",
              left: 50,
              top: 80,
              width: 660,
              height: 760,
              background: "#efe2b8",
              translate: `0 ${interpolate(doc, [0, 1], [380, -160])}px`,
              boxShadow: "0 10px 0 rgba(0,0,0,0.2)",
            }}
          >
            <div style={{ textAlign: "center", marginTop: 90, fontSize: 250, fontWeight: 900, color: C.ink, letterSpacing: -8 }}>
              1865
            </div>
            {[0, 1, 2, 3].map((i) => (
              <div key={i} style={{ margin: "34px 60px 0", height: 12, background: "#d6c79a", width: `${55 + rnd(i + 4) * 35}%` }} />
            ))}
          </div>
          {/* old qopqoq */}
          <div
            style={{
              position: "absolute",
              top: 220,
              left: 0,
              width: 760,
              height: 680,
              background: C.cream,
              borderRadius: 12,
              transformOrigin: "bottom center",
              transform: `perspective(1400px) rotateX(${open * -12}deg)`,
              boxShadow: "0 -6px 0 rgba(0,0,0,0.12)",
            }}
          />
        </div>
      </div>
      <div style={{ ...center, top: 960 }}>
        <Stamp at={2.4} size={150} rotate={-12}>SIR</Stamp>
      </div>
      {/* chang zarrachalari */}
      {Array.from({ length: 22 }).map((_, i) => {
        const k = p(t, 2.45, 1.1);
        const ang = rnd(i) * Math.PI * 2;
        const dist = 120 + rnd(i + 9) * 320;
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: 540,
              top: 1010,
              width: 10 + rnd(i + 2) * 12,
              height: 10 + rnd(i + 2) * 12,
              borderRadius: 99,
              background: C.cream,
              opacity: (1 - k) * (t > 2.45 ? 0.8 : 0),
              translate: `${Math.cos(ang) * dist * k}px ${Math.sin(ang) * dist * k - 40 * k}px`,
            }}
          />
        );
      })}
    </Stage>
  );
};

/* ---------- 3 · Finlyandiya, sharshara, muhandis ---------- */
const FIN =
  "M470 130 L560 110 L640 170 L610 270 L690 360 L650 470 L700 580 L640 700 L560 760 L470 740 L420 660 L440 560 L380 480 L400 380 L350 300 L400 220 Z";

export const Scene3: React.FC = () => {
  const t = useSec();
  const mapIn = p(t, 0, 0.8);
  const river = p(t, 1.0, 2.0, Easing.inOut(Easing.quad));
  const eng = p(t, 3.4, 0.7, easeBack);
  return (
    <Stage dur={DUR[2]}>
      <Sfx at={0} src="whoosh" volume={0.5} />
      <Sfx at={1.2} src="paper" volume={0.6} />
      <Sfx at={3.5} src="click" />
      <Sfx at={4.3} src="blip" volume={0.5} />
      <div style={{ ...center, top: 220, opacity: mapIn }}>
        <svg width="900" height="1000" viewBox="300 60 500 760">
          <path d={FIN} fill="none" stroke={C.cream} strokeWidth="5" strokeLinejoin="round" />
          {[18, 36, 54].map((o) => (
            <path key={o} d={FIN} fill="none" stroke={C.cream} strokeOpacity={0.3 - o / 260} strokeWidth="3" transform={`translate(${o * 2.2} ${o * 1.1}) scale(${1 - o / 280})`} style={{ transformOrigin: "520px 420px" }} />
          ))}
          <path
            d="M430 240 C470 300 520 330 540 400 C560 470 500 520 520 600 C530 650 560 690 580 720"
            fill="none"
            stroke="#5aa6d8"
            strokeWidth="14"
            strokeLinecap="round"
            pathLength={1}
            strokeDasharray={1}
            strokeDashoffset={1 - river}
          />
          <circle cx="520" cy="600" r="14" fill={C.orange} opacity={river > 0.85 ? 1 : 0} />
          <circle cx="520" cy="600" r={14 + (t * 40) % 36} fill="none" stroke={C.orange} strokeWidth="3" opacity={river > 0.85 ? 1 - ((t * 40) % 36) / 36 : 0} />
          <text x="470" y="100" fill={C.cream} fontSize="34" fontWeight="900" letterSpacing="4">FINLYANDIYA</text>
        </svg>
      </div>
      {/* sharshara + g'o'lalar */}
      <div style={{ position: "absolute", left: 640, top: 1000, opacity: p(t, 2.5, 0.5) }}>
        {Array.from({ length: 8 }).map((_, i) => {
          const k = ((t * 0.9 + i / 8) % 1);
          return (
            <div key={i} style={{ position: "absolute", left: rnd(i) * 40, top: k * 260, width: 54, height: 18, borderRadius: 9, background: "#a8744a", rotate: `${rnd(i + 3) * 40 - 20}deg`, opacity: Math.min(1, k * 6) }} />
          );
        })}
        {Array.from({ length: 14 }).map((_, i) => (
          <div key={`w${i}`} style={{ position: "absolute", left: i * 7 - 20, top: ((t * 3 + i * 0.27) % 1) * 280, width: 4, height: 60, background: "#8cc4ea", opacity: 0.6, borderRadius: 4 }} />
        ))}
      </div>
      {/* muhandis silueti */}
      <div style={{ position: "absolute", left: 120, top: 980, scale: String(eng), transformOrigin: "bottom center", opacity: eng }}>
        <div style={{ position: "relative", width: 230, height: 440 }}>
          <div style={{ position: "absolute", left: 55, top: 0, width: 120, height: 14, background: C.cream, borderRadius: 4 }} />
          <div style={{ position: "absolute", left: 75, top: -62, width: 80, height: 70, background: C.cream, borderRadius: "10px 10px 0 0" }} />
          <div style={{ position: "absolute", left: 70, top: 10, width: 90, height: 90, background: C.creamDark, borderRadius: 99 }} />
          <div style={{ position: "absolute", left: 20, top: 100, width: 190, height: 340, background: C.cream, borderRadius: "70px 70px 6px 6px" }} />
        </div>
      </div>
      <div style={{ ...center, top: 1500, scale: String(p(t, 3.9, 0.5, easeBack)), opacity: p(t, 3.9, 0.2) }}>
        <Tag size={64}>Fredrik Idestam</Tag>
      </div>
      <div style={{ position: "absolute", left: 70, top: 200, opacity: p(t, 0.3, 0.5) }}>
        <Tag color={C.orange} size={52}>1865</Tag>
      </div>
    </Stage>
  );
};

/* ---------- 4 · Tegirmon kesimi ---------- */
export const Scene4: React.FC = () => {
  const t = useSec();
  const wheel = t * 70;
  const grind = t * 220;
  const roll = p(t, 1.5, 3.5, Easing.linear);
  return (
    <Stage dur={DUR[3]}>
      <Sfx at={0} src="whoosh" volume={0.5} />
      <Sfx at={0.8} src="tick" />
      <Sfx at={1.4} src="tick" />
      <Sfx at={2.0} src="tick" />
      <Sfx at={2.6} src="tick" />
      <Sfx at={3.2} src="tick" />
      <Sfx at={3.8} src="paper" volume={0.6} />
      <Sfx at={4.5} src="ding" volume={0.5} />
      <div style={{ ...center, top: 330 }}>
        <svg width="1000" height="1000" viewBox="0 0 1000 1000">
          {/* bino */}
          <rect x="140" y="160" width="720" height="560" fill={C.cream} />
          <polygon points="110,160 500,20 890,160" fill={C.orange} />
          <rect x="140" y="560" width="720" height="160" fill={C.creamDark} />
          {/* suv */}
          <rect x="0" y="720" width="1000" height="180" fill="#3b7fb0" />
          {[0, 1, 2, 3, 4].map((i) => (
            <path key={i} d={`M${i * 220 - ((t * 120) % 220)} 760 q55 -26 110 0 t110 0`} stroke="#8cc4ea" strokeWidth="8" fill="none" />
          ))}
          {/* suv g'ildiragi */}
          <g transform={`translate(110 610) rotate(${wheel})`}>
            <circle r="150" fill="none" stroke="#6b4a2a" strokeWidth="18" />
            {Array.from({ length: 8 }).map((_, i) => (
              <rect key={i} x="-8" y="-150" width="16" height="300" fill="#6b4a2a" transform={`rotate(${i * 22.5})`} />
            ))}
            <circle r="22" fill="#3a2812" />
          </g>
          {/* g'o'lalar tasmasi */}
          <rect x="200" y="420" width="260" height="22" fill="#3a2812" />
          {Array.from({ length: 4 }).map((_, i) => {
            const k = (t * 0.55 + i / 4) % 1;
            return <rect key={i} x={170 + k * 250} y={380} width="80" height="36" rx="16" fill="#a8744a" />;
          })}
          {/* tegirmon toshi */}
          <g transform={`translate(560 400) rotate(${grind})`}>
            <circle r="95" fill="#8a8f9c" />
            <circle r="95" fill="none" stroke="#5c616d" strokeWidth="8" />
            <rect x="-6" y="-95" width="12" height="190" fill="#5c616d" />
            <rect x="-95" y="-6" width="190" height="12" fill="#5c616d" />
          </g>
          {/* massa -> varaq -> rulon */}
          <rect x="650" y="470" width={80 + roll * 120} height="16" fill={C.cream} stroke={C.creamDark} />
          <g transform="translate(820 470)">
            <circle r={30 + roll * 70} fill={C.cream} stroke={C.creamDark} strokeWidth="6" />
            <circle r={30 + roll * 70 - 18} fill="none" stroke={C.creamDark} strokeWidth="3" />
          </g>
        </svg>
      </div>
      <div style={{ ...center, top: 1380, scale: String(p(t, 2.6, 0.5, easeBack)) }}>
        <Tag size={62} color={C.orange}>Qog&apos;oz massasi</Tag>
      </div>
    </Stage>
  );
};

/* ---------- 5 · Nokia shaharchasi belgisi ---------- */
export const Scene5: React.FC = () => {
  const t = useSec();
  const drop = p(t, 0.2, 0.7, Easing.bounce);
  const sway = Math.sin(t * 2) * 3;
  const txt = p(t, 2.0, 0.7);
  return (
    <Stage dur={DUR[4]}>
      <Sfx at={0.1} src="whoosh" volume={0.5} />
      <Sfx at={0.55} src="boom" volume={0.6} />
      <Sfx at={2.1} src="blip" volume={0.6} />
      <Sfx at={3.3} src="ding" volume={0.5} />
      {/* daryo */}
      <div style={{ position: "absolute", left: 0, right: 0, top: 1180, height: 360, background: "#3b7fb0" }}>
        <svg width="1080" height="360">
          {[0, 1, 2, 3].map((r) => (
            <path key={r} d={`M${-((t * 160 + r * 90) % 240)} ${60 + r * 80} ${Array.from({ length: 8 }).map(() => "q60 -28 120 0 t120 0").join(" ")}`} stroke="#8cc4ea" strokeWidth="8" fill="none" />
          ))}
        </svg>
      </div>
      <div style={{ position: "absolute", left: 0, right: 0, top: 1130, height: 70, background: "#4a6b3a" }} />
      {/* belgi */}
      <div style={{ ...center, top: 360, translate: `0 ${interpolate(drop, [0, 1], [-900, 0])}px`, rotate: `${sway}deg` }}>
        <div style={{ position: "relative", width: 700, height: 800 }}>
          <div style={{ position: "absolute", left: 320, top: 120, width: 60, height: 680, background: "#6b4a2a" }} />
          <div style={{ position: "absolute", left: 0, top: 0, width: 700, height: 230, background: "#b9895a", borderRadius: 14, boxShadow: "0 14px 0 rgba(0,0,0,0.3)", display: "flex", alignItems: "center", justifyContent: "center", color: C.ink, fontWeight: 900, fontSize: 150, letterSpacing: 6 }}>
            NOKIA
          </div>
        </div>
      </div>
      <div style={{ ...center, top: 1280, translate: `0 ${interpolate(txt, [0, 1], [120, 0])}px`, opacity: txt }}>
        <Band color={C.orange} size={82} rotate={-2}>Nokia = shaharcha</Band>
      </div>
      <div style={{ position: "absolute", left: 100, top: 1560, opacity: p(t, 3.0, 0.5) }}>
        <Tag size={44}>Nokianvirta daryosi</Tag>
      </div>
    </Stage>
  );
};
