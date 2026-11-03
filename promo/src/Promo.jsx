import React from "react";
import {
  AbsoluteFill,
  Audio,
  Img,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import script from "../script.json";

const COLORS = {
  paper: "#f7f4eb",
  ink: "#26332f",
  teal: "#71cabb",
  coral: "#e58f70",
  gold: "#e9c66b",
  lavender: "#b5a7d6",
  muted: "#68716b",
};

const sceneAt = (seconds) =>
  script.scenes.find(
    (scene) => seconds >= scene.start && seconds < scene.start + scene.duration,
  ) || script.scenes.at(-1);

function Character({ kind, x, y, scale = 1, expression = "neutral" }) {
  const ripple = kind === "ripple";
  return (
    <svg
      aria-hidden="true"
      style={{ position: "absolute", left: x, top: y, width: 220 * scale, height: 300 * scale, overflow: "visible" }}
      viewBox={ripple ? "0 0 300 340" : "0 0 260 500"}
    >
      {ripple ? (
        <g transform="translate(22 30)">
          <path d="M128 280C70 280 35 241 42 177C48 116 84 68 128 30C172 68 208 116 214 177C221 241 186 280 128 280Z" fill={COLORS.teal} stroke={COLORS.ink} strokeWidth="10" />
          <path d="M128 80C118 119 118 160 121 190C122 214 108 229 94 225C80 221 82 204 95 199C109 194 122 210 133 224" fill="none" stroke={COLORS.ink} strokeWidth="10" strokeLinecap="round" />
          <path d="M79 151Q95 140 109 151M148 151Q164 140 178 151" fill="none" stroke={COLORS.ink} strokeWidth="10" strokeLinecap="round" />
          <circle cx="96" cy="174" r="8" fill={COLORS.ink} /><circle cx="162" cy="174" r="8" fill={COLORS.ink} />
          <path d={expression === "sheepish" ? "M111 210Q128 202 145 210" : "M108 209Q128 227 148 208"} fill="none" stroke={COLORS.ink} strokeWidth="10" strokeLinecap="round" />
          <path d="M82 275Q72 306 48 309Q76 324 101 296M174 275Q184 306 208 309Q180 324 155 296" fill={COLORS.gold} stroke={COLORS.ink} strokeWidth="10" strokeLinejoin="round" />
        </g>
      ) : (
        <g transform="translate(20 10)">
          <path d="M48 90Q30 46 70 24Q101 3 127 26Q157 3 183 32Q218 30 230 70L209 91Q173 65 134 72Q88 64 48 90Z" fill={COLORS.ink} />
          <ellipse cx="135" cy="128" rx="76" ry="76" fill={COLORS.paper} stroke={COLORS.ink} strokeWidth="10" />
          <path d="M98 127Q111 117 124 127M146 127Q159 117 172 127" fill="none" stroke={COLORS.ink} strokeWidth="10" strokeLinecap="round" />
          <path d="M95 110Q111 98 126 109M145 109Q161 98 176 110" fill="none" stroke={COLORS.ink} strokeWidth="9" strokeLinecap="round" />
          <path d="M112 160Q135 149 158 160M135 205V390M134 240Q83 277 53 335M136 240Q187 277 218 335M135 390Q97 448 78 490M135 390Q174 448 194 490" fill="none" stroke={COLORS.ink} strokeWidth="10" strokeLinecap="round" strokeLinejoin="round" />
        </g>
      )}
    </svg>
  );
}

function Caption({ scene, language }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const seconds = frame / fps;
  const caption = scene.captions[language].find(
    (item) => seconds >= item.start && seconds < item.end,
  );
  if (!caption) return null;
  return (
    <div
      dir={language === "ar" ? "rtl" : "ltr"}
      style={{
        position: "absolute",
        left: "10%",
        right: "10%",
        bottom: "20%",
        color: COLORS.paper,
        background: COLORS.ink,
        border: `4px solid ${COLORS.teal}`,
        borderRadius: 18,
        padding: "22px 30px",
        fontFamily: language === "ar" ? "Noto Sans Arabic, sans-serif" : "DM Sans, sans-serif",
        fontSize: 48,
        lineHeight: 1.18,
        fontWeight: 700,
        textAlign: language === "ar" ? "right" : "left",
        boxShadow: "8px 8px 0 rgba(38,51,47,.18)",
      }}
    >
      {caption.text}
    </div>
  );
}

function BrowserCard({ src, label, style }) {
  return (
    <div style={{ position: "absolute", overflow: "hidden", border: `6px solid ${COLORS.ink}`, borderRadius: 22, background: COLORS.paper, ...style }}>
      <div style={{ height: 32, background: COLORS.ink, color: COLORS.paper, padding: "5px 16px", font: "700 18px DM Sans" }}>{label}</div>
      <Img src={staticFile(`captures/${src}`)} style={{ width: "100%", display: "block" }} />
    </div>
  );
}

function Scene({ scene, reducedMotion, language }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const local = frame - scene.start * fps;
  const wobble = reducedMotion ? 0 : Math.sin(local / 5) * 3;
  const appear = interpolate(local, [0, 12], [0, 1], { extrapolateRight: "clamp" });
  const common = { background: COLORS.paper, color: COLORS.ink };
  if (scene.id === "hook") return <AbsoluteFill style={common}><div style={{ position: "absolute", left: "8%", top: "12%", font: "700 28px DM Sans", color: COLORS.teal }}>01 · AGAIN?</div><div style={{ position: "absolute", left: "16%", top: 380, width: 680, height: 450, border: `12px solid ${COLORS.ink}`, borderRadius: 28, background: COLORS.lavender, transform: `rotate(${wobble / 3}deg)` }}><div style={{ padding: 48, font: "700 40px DM Sans" }}>same paragraph<br /><span style={{ color: COLORS.teal }}>same problem</span></div></div><Character kind="re-explainer" x="65%" y="32%" scale={1.2} /><Caption scene={scene} language={language} /></AbsoluteFill>;
  if (scene.id === "problem") return <AbsoluteFill style={common}><div style={{ position: "absolute", top: 280, left: "8%", right: "8%", display: "flex", gap: 36, transform: `translateY(${wobble}px)` }}>{["CHAT A", "CHAT B", "CHAT C"].map((label, index) => <div key={label} style={{ flex: 1, height: 330, border: `10px solid ${COLORS.ink}`, borderRadius: 26, background: [COLORS.coral, COLORS.lavender, COLORS.gold][index], padding: 28, font: "700 38px DM Sans" }}>{label}<div style={{ marginTop: 70, fontSize: 28 }}>Explain it again?</div></div>)}</div><div style={{ position: "absolute", left: "10%", top: 790, font: "700 42px DM Sans" }}>tokens: <span style={{ color: COLORS.coral }}>{Math.min(2, 1 + Math.floor(local / (fps * 2)))}</span> <small>(example)</small></div><Character kind="re-explainer" x="68%" y="52%" scale=".75" expression="confused" /><Caption scene={scene} language={language} /></AbsoluteFill>;
  if (scene.id === "meet-lake") return <AbsoluteFill style={common}><svg style={{ position: "absolute", left: "20%", top: 170, width: 650, height: 700 }} viewBox="0 0 300 600"><path d="M150 20C125 20 112 45 110 88V245C110 290 110 350 110 450C108 500 80 540 55 535C30 530 34 500 58 492C84 483 110 507 132 530" fill="none" stroke={COLORS.ink} strokeWidth="12" strokeLinecap="round" strokeDasharray="1" strokeDashoffset={Math.max(0, 1 - appear) * 1000} pathLength="1000" /></svg><Character kind="ripple" x="53%" y="31%" scale="1.25" expression="happy" /><div style={{ position: "absolute", top: 820, width: "100%", textAlign: "center", font: "700 64px DM Sans", color: COLORS.teal }}>Lake</div><Caption scene={scene} language={language} /></AbsoluteFill>;
  if (scene.id === "demo") return <AbsoluteFill style={common}><BrowserCard src="01-welcome.png" label="welcome wall · demo" style={{ left: "6%", top: 130, width: "52%", opacity: 1 - Math.min(1, local / (fps * 3)) }} /><BrowserCard src="03-search.png" label="search · fictional library" style={{ left: "14%", top: 180, width: "66%", opacity: interpolate(local, [fps * 2, fps * 5], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }} /><BrowserCard src="05-context.png" label="continue from here" style={{ left: "22%", top: 220, width: "64%", opacity: interpolate(local, [fps * 8, fps * 11], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) }} /><Character kind="ripple" x="77%" y="58%" scale=".65" expression="celebrating" /><Caption scene={scene} language={language} /></AbsoluteFill>;
  if (scene.id === "privacy") return <AbsoluteFill style={common}><div style={{ position: "absolute", left: "12%", top: 260, width: "76%", height: 580, border: `7px dashed ${COLORS.teal}`, borderRadius: 50 }} /><div style={{ position: "absolute", left: "25%", top: 370, width: "50%", height: 270, border: `14px solid ${COLORS.ink}`, borderRadius: 25, background: COLORS.teal }}><div style={{ position: "absolute", left: "43%", top: 80, width: 110, height: 110, background: COLORS.gold, border: `10px solid ${COLORS.ink}`, borderRadius: 18 }} /></div><div style={{ position: "absolute", right: "6%", top: 210, font: "700 40px DM Sans", color: COLORS.coral, transform: "rotate(-12deg)" }}>NO CLOUD</div><Caption scene={scene} language={language} /></AbsoluteFill>;
  if (scene.id === "honest-bit") return <AbsoluteFill style={common}><Character kind="ripple" x="16%" y="32%" scale="1.05" expression="sheepish" /><div style={{ position: "absolute", left: "52%", top: 300, width: 520, height: 360, border: `10px solid ${COLORS.ink}`, borderRadius: 22, padding: 32, font: "700 34px DM Sans", background: COLORS.paper }}>original transcript<br /><span style={{ color: COLORS.teal }}>still here</span></div><div style={{ position: "absolute", left: "34%", top: 190, font: "700 38px DM Sans", color: COLORS.coral }}>local model?</div><Caption scene={scene} language={language} /></AbsoluteFill>;
  return <AbsoluteFill style={common}><Character kind="ripple" x="18%" y="34%" scale="1.1" expression="happy" /><Character kind="re-explainer" x="58%" y="29%" scale=".82" /><div style={{ position: "absolute", top: 160, width: "100%", textAlign: "center", font: "700 88px DM Sans", color: COLORS.teal }}>Lake</div><Caption scene={scene} language={language} /></AbsoluteFill>;
}

export function Promo({ language = "en", reducedMotion = false }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const scene = sceneAt(frame / fps);
  return <AbsoluteFill style={{ background: COLORS.paper }}><style>{`@font-face{font-family:"DM Sans";src:url("${staticFile("dm-sans.woff2")}")}@font-face{font-family:"Noto Sans Arabic";src:url("${staticFile("arabic.woff2")}")}`}</style><Scene scene={scene} reducedMotion={reducedMotion} language={language} />{!reducedMotion && <Audio src={staticFile("sound-design.wav")} volume={0.18} />}</AbsoluteFill>;
}
