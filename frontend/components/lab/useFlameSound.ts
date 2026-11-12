"use client";
import { useEffect, useRef } from "react";

/* Sound for the flame, generated in the browser (no audio files). Four quiet layers, each tied to a number:
     cabin hum   constant, very low
     airflow     louder and brighter with the airflow slider
     flame       a soft roar that swells with the burning rate and fades as the flame dies
     breathing   slow and easy in good air; faster and heavier as oxygen falls below what lungs need
   Off until the reader turns it on. Everything eases, nothing clicks. */

export interface SoundState { life: number; heat: number; flow: number; strain: number }

export function useFlameSound(on: boolean, s: SoundState) {
  const nodes = useRef<any>(null);
  const latest = useRef(s);
  latest.current = s;

  useEffect(() => {
    if (!on) return;
    const AC = window.AudioContext || (window as any).webkitAudioContext;
    if (!AC) return;
    const ctx: AudioContext = new AC();
    const master = ctx.createGain();
    master.gain.value = 0;
    master.gain.linearRampToValueAtTime(0.55, ctx.currentTime + 1.2);
    master.connect(ctx.destination);

    // one buffer of brown noise, reused by every layer
    const len = ctx.sampleRate * 3, buf = ctx.createBuffer(1, len, ctx.sampleRate), d = buf.getChannelData(0);
    let b = 0;
    for (let i = 0; i < len; i++) { b = (b + 0.02 * (Math.random() * 2 - 1)) / 1.02; d[i] = b * 3.2; }
    const layer = (type: BiquadFilterType, freq: number, q: number, offset: number) => {
      const src = ctx.createBufferSource(); src.buffer = buf; src.loop = true;
      const f = ctx.createBiquadFilter(); f.type = type; f.frequency.value = freq; f.Q.value = q;
      const g = ctx.createGain(); g.gain.value = 0;
      src.connect(f); f.connect(g); g.connect(master); src.start(0, offset);
      return { f, g };
    };
    const flame = layer("lowpass", 420, 0.6, 0), air = layer("bandpass", 900, 0.5, 1.1), breath = layer("bandpass", 700, 1.1, 2.0);
    const hum = ctx.createGain(); hum.gain.value = 0.028; hum.connect(master);
    [55, 82.4].forEach((hz) => { const o = ctx.createOscillator(); o.type = "sine"; o.frequency.value = hz; o.connect(hum); o.start(); });

    // breathing: one inhale and one exhale per cycle, scheduled a cycle ahead
    let alive = true, timer: any;
    const breathe = () => {
      if (!alive) return;
      const strain = latest.current.strain, T = 4.4 - 2.0 * strain, peak = 0.05 + 0.2 * strain, t0 = ctx.currentTime + 0.05;
      const g = breath.g.gain, f = breath.f.frequency;
      g.cancelScheduledValues(t0); g.setValueAtTime(0.0001, t0);
      f.setValueAtTime(950, t0);
      g.linearRampToValueAtTime(peak, t0 + T * 0.32); g.linearRampToValueAtTime(0.0001, t0 + T * 0.42);       // in
      f.setValueAtTime(520, t0 + T * 0.46);
      g.linearRampToValueAtTime(peak * 0.8, t0 + T * 0.58); g.linearRampToValueAtTime(0.0001, t0 + T * 0.92); // out
      timer = setTimeout(breathe, T * 1000);
    };
    breathe();
    nodes.current = { ctx, flame, air };
    return () => {
      alive = false; clearTimeout(timer); nodes.current = null;
      master.gain.cancelScheduledValues(ctx.currentTime);
      master.gain.setTargetAtTime(0, ctx.currentTime, 0.08);
      setTimeout(() => ctx.close().catch(() => {}), 400);
    };
  }, [on]);

  useEffect(() => {
    const n = nodes.current;
    if (!n) return;
    const t = n.ctx.currentTime;
    n.flame.g.gain.setTargetAtTime(s.life * (0.10 + 0.34 * s.heat), t, 0.25);
    n.flame.f.frequency.setTargetAtTime(260 + 900 * s.heat, t, 0.3);
    n.air.g.gain.setTargetAtTime(0.02 + 0.22 * s.flow, t, 0.2);
    n.air.f.frequency.setTargetAtTime(600 + 1400 * s.flow, t, 0.3);
  }, [on, s.life, s.heat, s.flow]);
}
