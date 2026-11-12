"use client";
import { useEffect, useRef, useState } from "react";
import HeroFlame, { FlameState } from "./HeroFlame";

/* The flame, drawn on the GPU. One fragment shader paints a dark cabin, the fuel (a floating
   droplet on its fibre, or a slab of material) and a volumetric-looking flame whose size, colour,
   lean and stretch follow the same six numbers as the flat version:
     life (is it burning), heat (how hard), warm (blue → amber), flow, gravity, drop (droplet size).
   It is an illustration shaped by the model and the measurements, not a combustion simulation.
   Falls back to the flat canvas flame when WebGL is unavailable, and lowers its own resolution
   if the machine cannot hold a smooth frame rate. */

export type SceneOverride = Partial<Pick<FlameState, "p" | "heat" | "o2" | "flow" | "gravity" | "known">> & { drop?: number };

const VERT = `attribute vec2 a; void main(){ gl_Position = vec4(a, 0., 1.); }`;
const FRAG = `
precision highp float;
uniform vec2 u_res; uniform float u_time, u_life, u_heat, u_warm, u_flow, u_g, u_drop, u_mode, u_known;

float hash(vec2 p){ p = fract(p * vec2(123.34, 456.21)); p += dot(p, p + 45.32); return fract(p.x * p.y); }
float noise(vec3 x){
  vec3 i = floor(x), f = fract(x); f = f * f * (3. - 2. * f);
  float n = i.x + i.y * 57. + i.z * 113.;
  #define H(o) fract(sin(n + o) * 43758.5453)
  return mix(mix(mix(H(0.), H(1.), f.x), mix(H(57.), H(58.), f.x), f.y),
             mix(mix(H(113.), H(114.), f.x), mix(H(170.), H(171.), f.x), f.y), f.z);
}
float fbm(vec3 p){ float a = .5, s = 0.; for (int i = 0; i < 4; i++){ s += a * noise(p); p = p * 2.03 + 7.1; a *= .5; } return s; }

// flame colour from how hot a point is (0 edge … 1 core) and how warm the flame is overall
// (0 = starved, blue, microgravity; 1 = vigorous, amber). Edges stay saturated; only the core goes pale.
vec3 ramp(float I, float w0){
  float w = smoothstep(.36, .64, w0);
  vec3 edge = mix(vec3(.05, .16, .75), vec3(.80, .16, .02), w);
  vec3 mid  = mix(vec3(.25, .58, 1.), vec3(1., .56, .14), w);
  vec3 core = mix(vec3(.78, .90, 1.), vec3(1., .90, .66), w);
  vec3 c = mix(edge, mid, smoothstep(.10, .55, I));
  c = mix(c, core, smoothstep(.72, 1.08, I));
  return c * smoothstep(.02, .34, I) * min(1., .30 + I);
}

void main(){
  vec2 uv = (gl_FragCoord.xy - .5 * u_res) / min(u_res.x, u_res.y);
  // the cabin: near-black with a faint vignette, and a few soft stars through the window
  vec3 col = vec3(.018, .024, .042) * (1.2 - 1.1 * dot(uv, uv));
  vec2 cell = floor(uv * 34.), cf = fract(uv * 34.) - .5;
  float star = step(.94, hash(cell)) * smoothstep(.09, .0, length(cf - (vec2(hash(cell + 1.7), hash(cell + 9.3)) - .5) * .6));
  col += vec3(.75, .82, 1.) * star * .30 * (1. - .7 * u_life);

  float life = u_life;
  vec3 glow = vec3(0.);

  if (u_mode > .5) {
    // ---- droplet: liquid sphere on a fibre, with the flame as a shell standing off it
    vec2 q = uv - vec2(0., .02);
    float Rd = .004 + .096 * u_drop;
    float up = max(q.y, 0.);
    vec2 sq = vec2(q.x * (1. + .9 * u_g * smoothstep(0., .5, up)), q.y > 0. ? q.y / (1. + 1.7 * u_g) : q.y * (1. + .35 * u_g));
    float r = length(sq);
    float Rf = Rd * (3.5 - 1.25 * u_warm) * (.5 + .5 * life);
    float n = fbm(vec3(q * 7. + vec2(0., -u_time * (.22 + 1.4 * u_g)), u_time * .3));
    float n2 = fbm(vec3(q * 19., u_time * .55));
    float w = Rf * (.11 + .05 * u_heat);
    float shell = exp(-pow((r - Rf * (1. + .12 * (n - .5))) / w, 2.)) * (.82 + .36 * n2);
    float inner = smoothstep(Rf, Rd, r) * .16;
    float halo = exp(-r * r / (Rf * Rf * 2.0)) * .16;
    glow = ramp((shell * (.78 + .30 * u_heat) + inner + halo) * life, u_warm);
    // fibre holding the droplet
    col += vec3(.10, .12, .16) * smoothstep(.0022, .0, abs(q.y)) * smoothstep(Rd, Rd + .01, abs(q.x)) * smoothstep(.62, .40, abs(q.x));
    // liquid: a dark sphere lit on its rim by its own flame
    float d = length(q), z = sqrt(max(0., 1. - (d * d) / (Rd * Rd)));
    vec3 liq = vec3(.035, .05, .075) + ramp(.62, u_warm) * pow(1. - z, 2.4) * (.15 + .95 * life);
    liq += vec3(1.) * smoothstep(.10, .0, length(q / Rd - vec2(-.36, .40))) * .35;
    float inside = smoothstep(Rd + .003, Rd - .003, d);
    col = mix(col, liq, inside);
    glow *= 1. - .88 * inside;
  } else {
    // ---- solid: a slab of material with the flame sitting on it
    vec2 base = vec2(0., -.2), f = uv - base;
    float H = .12 + .46 * u_g + .10 * u_heat + .05 * u_flow;
    float W = (.085 + .095 * u_heat) * (.55 + .45 * life);
    float hy = clamp(f.y / H, 0., 1.);
    float sway = (fbm(vec3(f.y * 3., u_time * .8, 4.)) - .5) * .05 * hy * (.3 + u_g);
    float fx = f.x - u_flow * .62 * max(f.y, 0.) * (1. - .55 * u_g) - sway;
    float taper = mix(1., 1. - .80 * pow(hy, .8), clamp(u_g, 0., 1.));
    float e = length(vec2(fx / (W * taper + .0001), f.y / H));
    float rise = u_time * (.45 + 2.6 * u_g + 1.3 * u_flow);
    float n = fbm(vec3(fx * 9., f.y * 7. - rise, u_time * .30));
    float n2 = fbm(vec3(fx * 22., f.y * 15. - rise * 1.7, u_time * .5));
    float field = (1. - e) + (n - .5) * .75 * (.30 + .70 * hy) + (n2 - .5) * .22 * hy;
    float body = smoothstep(.02, .50, field) * smoothstep(-.006, .004, f.y);
    float hot = body * (.40 + .52 * (1. - hy) * clamp(1. - 1.1 * abs(fx) / (W + .001), 0., 1.) + .10 * u_heat) * (.75 + .5 * n2);
    float warmHere = clamp(u_warm + .30 * u_g * hy - .55 * (1. - smoothstep(0., .14, hy)) * (.35 + .65 * u_g), 0., 1.);   // blue at the very base
    float halo = exp(-(fx * fx + (f.y - H * .35) * (f.y - H * .35)) / (W * W * 2.6 + H * H * .30)) * .13 * smoothstep(-.02, .04, f.y);
    glow = ramp((hot + halo) * life, warmHere);
    // a dying ember when the flame is out but the case is known
    glow += vec3(1., .30, .10) * exp(-dot(f, f) / .0020) * (1. - life) * u_known * (.70 + .30 * sin(u_time * 3.));
    // air moving past, left to right
    float rows = 15., ry = (uv.y + .5) * rows, row = floor(ry);
    float x = fract(uv.x * .8 - u_time * (.10 + .95 * u_flow) + hash(vec2(row, 3.)));
    float dash = smoothstep(0., .03, x) * smoothstep(.12 + .12 * u_flow, .08 + .12 * u_flow, x);
    col += vec3(.40, .50, .66) * dash * smoothstep(.06, .0, abs(fract(ry) - .5)) * u_flow * .26 * step(base.y + .03, uv.y);
    // the slab, lit from above by the flame
    vec2 sl = abs(uv - vec2(0., base.y - .02)) - vec2(.44, .013);
    float slab = smoothstep(.004, .0, length(max(sl, 0.)) + min(max(sl.x, sl.y), 0.));
    vec3 slabCol = vec3(.20, .23, .29) * (.5 + .5 * smoothstep(-.03, .0, uv.y - base.y + .02))
                 + ramp(.6, warmHere) * life * exp(-uv.x * uv.x / (W * W * 10.)) * .55 * smoothstep(-.035, -.005, uv.y - base.y);
    col = mix(col, slabCol, slab);
    glow *= 1. - slab * .9;
  }
  col += glow * 1.12;
  col = 1. - exp(-col * 1.25);                    // filmic shoulder: bright without washing to white
  gl_FragColor = vec4(col, 1.);
}`;

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const clamp = (x: number) => Math.min(1, Math.max(0, x));

export default function FlameScene({ state, override }: { state: FlameState; override?: React.MutableRefObject<SceneOverride | null> }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const target = useRef(state);
  target.current = state;
  const [flat, setFlat] = useState(false);

  useEffect(() => {
    const cv = ref.current;
    if (!cv) return;
    const gl = cv.getContext("webgl", { antialias: false, alpha: false, powerPreference: "high-performance" });
    if (!gl) { setFlat(true); return; }
    const info = gl.getExtension("WEBGL_debug_renderer_info");
    const renderer = info ? String(gl.getParameter(info.UNMASKED_RENDERER_WEBGL)) : "";
    if (/swiftshader|llvmpipe|software|basic render/i.test(renderer) && !/[?&]gl=1/.test(window.location.search)) { setFlat(true); return; }
    const sh = (type: number, src: string) => { const s = gl.createShader(type)!; gl.shaderSource(s, src); gl.compileShader(s); return s; };
    const prog = gl.createProgram()!;
    const fs = sh(gl.FRAGMENT_SHADER, FRAG);
    gl.attachShader(prog, sh(gl.VERTEX_SHADER, VERT)); gl.attachShader(prog, fs); gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) { setFlat(true); return; }
    gl.useProgram(prog);
    gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(prog, "a");
    gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    const U = Object.fromEntries(["u_res", "u_time", "u_life", "u_heat", "u_warm", "u_flow", "u_g", "u_drop", "u_mode", "u_known"].map((n) => [n, gl.getUniformLocation(prog, n)]));

    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const cur = { life: 0, heat: 0.4, warm: 0.5, flow: 0, g: 0, drop: 1, known: 1 };
    let scale = Math.min(1.5, window.devicePixelRatio || 1), w = 0, h = 0, raf = 0, last = 0, acc = 0, frames = 0, t = 0;
    const size = () => { const r = cv.getBoundingClientRect(); w = Math.max(2, Math.round(r.width * scale)); h = Math.max(2, Math.round(r.height * scale)); cv.width = w; cv.height = h; gl.viewport(0, 0, w, h); };
    const ro = new ResizeObserver(size);
    ro.observe(cv);

    const frame = (now: number) => {
      const dt = last ? Math.min(100, now - last) : 16.7;
      last = now;
      // hold the frame rate: if the last 40 frames were slow, draw fewer pixels
      acc += dt; frames++;
      if (frames === 40) { if (acc / 40 > 22 && scale > 0.6) { scale = Math.max(0.6, scale * 0.8); size(); } acc = 0; frames = 0; }
      const s = { ...target.current, ...(override?.current ?? {}) } as FlameState & { drop?: number };
      const k = still ? 1 : 1 - Math.pow(0.0009, dt / 1000);          // frame-rate independent easing
      const life = s.known ? clamp((s.p - 0.2) / 0.45) : 0;
      cur.life = lerp(cur.life, life, k);
      cur.heat = lerp(cur.heat, s.heat, k);
      cur.warm = lerp(cur.warm, clamp(0.3 + clamp((s.o2 - 0.16) / 0.3) * 0.5 + s.gravity * 0.25 + s.flow * 0.2) * (0.35 + 0.65 * life), k);
      cur.flow = lerp(cur.flow, s.flow, k);
      cur.g = lerp(cur.g, s.gravity, k);
      cur.drop = lerp(cur.drop, s.drop ?? 0.6, override?.current ? 1 : k);
      cur.known = lerp(cur.known, s.known ? 1 : 0, k);
      if (!still) t += dt / 1000;
      gl.uniform2f(U.u_res, w, h); gl.uniform1f(U.u_time, t);
      gl.uniform1f(U.u_life, cur.life); gl.uniform1f(U.u_heat, cur.heat); gl.uniform1f(U.u_warm, cur.warm);
      gl.uniform1f(U.u_flow, cur.flow); gl.uniform1f(U.u_g, cur.g); gl.uniform1f(U.u_drop, cur.drop);
      gl.uniform1f(U.u_mode, s.mode === "droplet" ? 1 : 0); gl.uniform1f(U.u_known, cur.known);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    const lost = () => setFlat(true);
    cv.addEventListener("webglcontextlost", lost);
    return () => { cancelAnimationFrame(raf); ro.disconnect(); cv.removeEventListener("webglcontextlost", lost); };
  }, [override]);

  if (flat) return <HeroFlame state={state} />;
  return <canvas ref={ref} className="h-full w-full" role="img" aria-label="Illustrative flame that reacts to the conditions" data-scene="gl" />;
}
