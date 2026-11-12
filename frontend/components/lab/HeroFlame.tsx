"use client";
import { useEffect, useRef } from "react";

export interface FlameState {
  mode: "solid" | "droplet";
  p: number;          // chance of sustained burning, 0..1
  heat: number;       // 0..1: how vigorous (from the predicted rate)
  o2: number;         // oxygen fraction
  flow: number;       // 0..1 of the airflow slider (solids only)
  gravity: number;    // regime code
  known: boolean;     // false when the model has no nearby data
  drop?: number;      // 0..1 droplet size (droplet mode)
}

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const clamp = (x: number, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, x));
const mix = (c1: number[], c2: number[], t: number) => c1.map((v, i) => Math.round(lerp(v, c2[i], t)));
const BLUE = [90, 169, 255], AMBER = [255, 154, 61], CORE = [255, 243, 214];

/** The hero visual: an illustrative flame whose size, colour and shape follow the model in real time.
 *  Blue and round = weak, starved, microgravity; amber and stretched = vigorous, fed by airflow or buoyancy.
 *  It eases toward each new state so a slider move reads as the flame growing or dying, not jumping. */
export default function HeroFlame({ state }: { state: FlameState }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const target = useRef(state);
  target.current = state;

  useEffect(() => {
    const cv = ref.current!;
    const ctx = cv.getContext("2d")!;
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const cur = { life: 0, heat: 0.5, warm: 0.5, flow: 0, g: 0, known: 1 };
    let raf = 0, w = 0, h = 0, t0 = performance.now();
    // theme colours are read once and again only when the theme changes (getComputedStyle per frame is costly)
    let ink = "", line = "";
    const colours = () => { const css = getComputedStyle(cv); ink = css.getPropertyValue("--text-3").trim(); line = css.getPropertyValue("--line-strong").trim(); };
    colours();
    const themeWatch = new MutationObserver(colours);
    themeWatch.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    const ro = new ResizeObserver(() => {
      const r = cv.getBoundingClientRect(), d = 0.75;   // a soft glow is drawn below screen resolution and upscaled: 44% fewer pixels per frame
      w = r.width; h = r.height; cv.width = w * d; cv.height = h * d; ctx.setTransform(d, 0, 0, d, 0, 0);
    });
    ro.observe(cv);

    const glow = (x: number, y: number, r: number, rgb: number[], a: number) => {
      if (r <= 0 || a <= 0) return;
      const g = ctx.createRadialGradient(x, y, 0, x, y, r);
      g.addColorStop(0, `rgba(${rgb.join(",")},${a})`);
      g.addColorStop(1, `rgba(${rgb.join(",")},0)`);
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, r, 0, 7); ctx.fill();
    };

    const frame = (now: number) => {
      const s = target.current, t = (now - t0) / 1000, k = still ? 1 : 0.12;
      cur.life = lerp(cur.life, s.known ? clamp((s.p - 0.2) / 0.45) : 0, k);
      cur.heat = lerp(cur.heat, s.heat, k);
      cur.warm = lerp(cur.warm, clamp(0.3 + clamp((s.o2 - 0.16) / 0.3) * 0.5 + s.gravity * 0.25 + s.flow * 0.2) * (0.35 + 0.65 * clamp((s.p - 0.2) / 0.45)), k);
      cur.flow = lerp(cur.flow, s.flow, k);
      cur.g = lerp(cur.g, s.gravity, k);
      cur.known = lerp(cur.known, s.known ? 1 : 0, k);
      ctx.clearRect(0, 0, w, h);
      const cx = w / 2, base = h * 0.7, unit = Math.min(w, h) / 4.6;
      const flick = still ? 0 : Math.sin(t * 9) * 0.03 + Math.sin(t * 23.7) * 0.02;
      const body = mix(BLUE, AMBER, clamp(cur.warm));

      // airflow streaks (solids): speed and density follow the slider
      if (s.mode === "solid" && cur.flow > 0.01) {
        ctx.strokeStyle = line; ctx.lineWidth = 1.5; ctx.lineCap = "round";
        for (let i = 0; i < 9; i++) {
          const y = base - unit * (0.25 + i * 0.36), speed = 40 + cur.flow * 260;
          const x = ((t * speed + i * 137) % (w + 120)) - 60, len = 14 + cur.flow * 46;
          ctx.globalAlpha = 0.25 + cur.flow * 0.5;
          ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x + len, y); ctx.stroke();
        }
        ctx.globalAlpha = 1;
      }

      ctx.globalCompositeOperation = "lighter";
      if (s.mode === "solid") {
        // spine: buoyancy lifts it, airflow leans it downstream; with neither it stays a low dome
        const up = 0.35 + cur.g * 1.9 + cur.heat * 0.4, lean = cur.flow * 2.2 * (1 - cur.g * 0.6);
        const R = unit * (0.75 + cur.heat * 0.6) * (0.35 + 0.65 * cur.life) * (1 + flick);
        for (let i = 0; i < 9; i++) {
          const u = i / 8, r = R * (1 - Math.pow(u, 1.4) * 0.82);
          const wob = still ? 0 : Math.sin(t * 6 + u * 5) * unit * 0.05 * u;
          glow(cx + lean * unit * u * 1.4 + wob, base - unit * 0.1 - up * unit * u, r, body, 0.3 * cur.life);
        }
        glow(cx + lean * unit * 0.25, base - unit * 0.25, R * 0.55, CORE, 0.5 * cur.life * clamp(cur.warm + 0.2));
      } else {
        // droplet: a spherical shell standing off the liquid; it brightens and tightens as oxygen rises
        const rd = unit * 0.42, rf = rd * (3.6 - cur.warm * 1.3) * (0.6 + 0.4 * cur.life) * (1 + flick);
        const g = ctx.createRadialGradient(cx, base - unit * 1.2, rd, cx, base - unit * 1.2, rf * 1.25);
        g.addColorStop(0, `rgba(${body.join(",")},0)`);
        g.addColorStop(0.62, `rgba(${body.join(",")},${0.12 * cur.life})`);
        g.addColorStop(0.8, `rgba(${mix(body, CORE, 0.35).join(",")},${0.85 * cur.life})`);
        g.addColorStop(1, `rgba(${body.join(",")},0)`);
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(cx, base - unit * 1.2, rf * 1.25, 0, 7); ctx.fill();
      }
      ctx.globalCompositeOperation = "source-over";

      // what is burning
      if (s.mode === "solid") {
        ctx.fillStyle = ink; ctx.beginPath(); ctx.roundRect(cx - unit * 2.1, base, unit * 4.2, unit * 0.2, 4); ctx.fill();
        // a dying ember when the flame is out
        glow(cx, base, unit * 0.5, [200, 90, 40], 0.5 * (1 - cur.life) * cur.known);
      } else {
        ctx.fillStyle = ink; ctx.beginPath(); ctx.arc(cx, base - unit * 1.2, unit * 0.42, 0, 7); ctx.fill();
        ctx.strokeStyle = line; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.moveTo(cx - unit * 2.4, base - unit * 1.2); ctx.lineTo(cx + unit * 2.4, base - unit * 1.2); ctx.stroke();
      }
      // no nearby data: say so on the picture itself instead of drawing a confident flame
      if (cur.known < 0.5) {
        ctx.strokeStyle = ink; ctx.setLineDash([6, 8]); ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.arc(cx, base - unit * 1.1, unit * 1.3, 0, 7); ctx.stroke(); ctx.setLineDash([]);
        ctx.fillStyle = ink; ctx.font = `600 ${Math.round(unit * 0.9)}px sans-serif`; ctx.textAlign = "center"; ctx.textBaseline = "middle";
        ctx.fillText("?", cx, base - unit * 1.05);
      }
      if (!still) raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    const redraw = still ? setInterval(() => requestAnimationFrame(frame), 200) : null;   // reduced motion: static, updated on change
    return () => { cancelAnimationFrame(raf); ro.disconnect(); themeWatch.disconnect(); if (redraw) clearInterval(redraw); };
  }, []);

  return <canvas ref={ref} className="h-full w-full" role="img" aria-label="Illustrative flame that reacts to the conditions" />;
}
