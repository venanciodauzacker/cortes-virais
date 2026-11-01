import { loadFont } from "@remotion/fonts";
import React from "react";
import {
  AbsoluteFill,
  interpolate,
  interpolateColors,
  Sequence,
  staticFile,
  useCurrentFrame,
} from "remotion";

// Legendas do modelo henrico pro, modeladas nos 3 vídeos do enrico.delafiori.
// O python (legendas_pro.py) decide o que aparece e quando; aqui só o desenho e o movimento.
loadFont({ family: "Mont", url: staticFile("Montserrat-ExtraBold.ttf"), weight: "800" });
loadFont({ family: "MontMed", url: staticFile("Montserrat-Medium.ttf"), weight: "500" });

const AMARELO = "#FFD400";
const CINZA = "#8C8C8C";
const SOMBRA = "0 2px 16px rgba(0,0,0,0.55), 0 0 3px rgba(0,0,0,0.35)";
const DIN = "'DIN Condensed', 'Mont'";

type Palavra = { t: string; f: number; st?: "n" | "i" | "s" | "k" };
type Camada = { cam: "atras" | "frente" };
type Gancho = Camada & {
  k: "hook"; a: number; b: number; x: number; y: number; fs: number;
  lines: Palavra[][]; fin: { t: string; f: number; num: boolean; dx: number };
};
type Grande = Camada & {
  k: "big"; al?: "c" | "r" | "l"; a: number; b: number; t: string; x: number; y: number; fs: number;
  amarelo: boolean; num: boolean; meio: boolean;
};
type Lado = Camada & {
  k: "side"; a: number; b: number; x: number; y: number; fs: number;
  lado: "e" | "d"; lines: Palavra[][]; amarelos: string[];
};
type El = Gancho | Grande | Lado;
export type LegendasProps = { dur: number; els: El[]; camada: "atras" | "frente" };

// entrada de palavra: seca, com um pop rápido saindo do desfoque (3-4 quadros)
const pop = (d: number) => ({
  opacity: interpolate(d, [0, 1], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
  transform: `scale(${interpolate(d, [0, 2, 4], [0.84, 1.05, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })})`,
  filter: `blur(${interpolate(d, [0, 3], [5, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })}px)`,
});

// saída: desfoca e some nos últimos quadros
const saida = (frame: number, dur: number, n = 5) => {
  const r = dur - frame;
  return {
    opacity: interpolate(r, [0, n], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
    filter: `blur(${interpolate(r, [0, n], [8, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })}px)`,
  };
};

const GanchoEl: React.FC<{ e: Gancho }> = ({ e }) => {
  const frame = useCurrentFrame();
  const dur = e.b - e.a;
  const s = saida(frame, dur, 6);
  const zig = [0, 22, 6, 16, 2];
  const fd = frame - (e.fin.f - e.a);
  const amarelo = fd >= 8;
  const troca = fd >= 16; // a palavra final troca de fonte, como o "crédito" -> "CRÉDITO" dele
  const finCor = interpolateColors(fd, [8, 11], ["#FFFFFF", AMARELO]);
  return (
    <div style={{ position: "absolute", left: e.x, top: e.y, opacity: s.opacity, filter: s.filter }}>
      {e.lines.map((lin, li) => (
        <div key={li} style={{ marginLeft: zig[li % zig.length], lineHeight: 0.84, whiteSpace: "nowrap" }}>
          {lin.map((p, pi) => {
            const d = frame - (p.f - e.a);
            if (d < 0) return null;
            const fs = p.st === "s" ? e.fs * 0.56 : p.st === "i" ? e.fs * 0.78 : e.fs;
            return (
              <span
                key={pi}
                style={{
                  display: "inline-block", marginRight: e.fs * 0.18, transformOrigin: "left bottom",
                  fontFamily: "Mont", fontWeight: 800, fontSize: fs, letterSpacing: "-0.035em",
                  color: p.st === "k" ? AMARELO : "#FFFFFF", textShadow: SOMBRA,
                  fontStyle: p.st === "i" ? "italic" : "normal",
                  textDecoration: p.st === "i" ? "underline" : p.st === "k" ? "line-through" : "none",
                  textDecorationThickness: p.st === "k" ? fs * 0.08 : fs * 0.05,
                  textDecorationColor: p.st === "k" ? AMARELO : "#FFFFFF",
                  textUnderlineOffset: fs * 0.08,
                  ...pop(d),
                }}
              >
                {p.t}
              </span>
            );
          })}
        </div>
      ))}
      {fd >= 0 ? (
        <div
          style={{
            marginLeft: e.fin.dx, marginTop: e.fs * 0.02, lineHeight: 0.9, whiteSpace: "nowrap",
            fontFamily: troca || e.fin.num ? DIN : "Mont", fontWeight: 800,
            fontSize: e.fin.num ? e.fs * 2.1 : troca ? e.fs * 1.75 : e.fs * 1.38,
            letterSpacing: troca || e.fin.num ? "0" : "-0.04em",
            textTransform: troca || e.fin.num ? "uppercase" : "none",
            color: amarelo ? finCor : "#FFFFFF", textShadow: SOMBRA, transformOrigin: "left center",
            ...pop(fd),
          }}
        >
          {e.fin.t}
        </div>
      ) : null}
    </div>
  );
};

const GrandeEl: React.FC<{ e: Grande }> = ({ e }) => {
  const frame = useCurrentFrame();
  return (
    <div
      style={{
        position: "absolute", left: e.x, top: e.y,
        // "r": a palavra termina no x (encosta na cabeça pela esquerda); "l": começa no x
        transform: e.al === "r" ? "translate(-100%, -50%)" : e.al === "l" ? "translate(0, -50%)" : "translate(-50%, -50%)",
        whiteSpace: "nowrap",
      }}
    >
      <div
        style={{
          fontFamily: e.num ? DIN : "Mont", fontWeight: 800, fontSize: e.fs,
          letterSpacing: e.num ? "0" : "-0.035em", lineHeight: 1,
          color: e.amarelo ? AMARELO : "#FFFFFF", textShadow: SOMBRA,
          ...pop(frame),
        }}
      >
        {e.num ? e.t.toUpperCase() : e.t}
      </div>
    </div>
  );
};

const LadoEl: React.FC<{ e: Lado }> = ({ e }) => {
  const frame = useCurrentFrame();
  const dur = e.b - e.a;
  const s = saida(frame, dur, 6);
  return (
    <div
      style={{
        position: "absolute", top: e.y, opacity: s.opacity, filter: s.filter,
        ...(e.lado === "e" ? { right: 912 - e.x, textAlign: "right" } : { left: e.x, textAlign: "left" }),
      }}
    >
      {e.lines.map((lin, li) => (
        <div key={li} style={{ lineHeight: 1.02, whiteSpace: "nowrap" }}>
          {lin.map((p, pi) => {
            const d = frame - (p.f - e.a);
            if (d < 0) return <span key={pi} />;
            const alvo = e.amarelos.includes(p.t) ? AMARELO : "#FFFFFF";
            return (
              <span
                key={pi}
                style={{
                  display: "inline-block", marginLeft: pi ? e.fs * 0.26 : 0,
                  fontFamily: "Mont", fontWeight: 800, fontSize: e.fs, letterSpacing: "-0.02em",
                  color: interpolateColors(d, [0, 5], [CINZA, alvo]), textShadow: SOMBRA,
                  opacity: interpolate(d, [0, 2], [0, 1], { extrapolateRight: "clamp" }),
                  transform: `translateY(${interpolate(d, [0, 4], [7, 0], { extrapolateRight: "clamp" })}px)`,
                }}
              >
                {p.t}
              </span>
            );
          })}
        </div>
      ))}
    </div>
  );
};

export const Legendas: React.FC<LegendasProps> = ({ els, camada }) => {
  return (
    <AbsoluteFill style={{ backgroundColor: "transparent" }}>
      {els.filter((e) => e.cam === camada).map((e, i) => (
        <Sequence key={i} from={e.a} durationInFrames={Math.max(1, e.b - e.a)} layout="none">
          {e.k === "hook" ? <GanchoEl e={e} /> : e.k === "big" ? <GrandeEl e={e} /> : <LadoEl e={e} />}
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
