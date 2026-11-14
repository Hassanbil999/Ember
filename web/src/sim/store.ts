/* Simulator state outside React: parameters, the computed series, the timeline and the reference points.
   React components subscribe to `version`; the animation loop reads fields directly every frame, so playing
   the timeline never re-renders React (the playhead and clock are updated through onTick listeners). */
import { useSyncExternalStore } from 'react';
import type { Material, ModelParams, ModelParamsResponse, Preset, TestPoint } from '../types';
import { api } from '../api';
import { DEFAULT_PARAMS, simulate, type Series, type SimState } from './model';

export interface SimParams extends SimState { preset: string; compare: string | null }
export interface Timeline { t: number; t1: number; t2: number; playing: boolean; speed: number }

class SimStore {
  params: SimParams = { g: 0.166, o2: 34, p: 8.2, u: 10, mat: 'fabric', preset: 'moon', compare: null };
  modelParams: Record<Material, ModelParams> = DEFAULT_PARAMS;
  paramsMeta: ModelParamsResponse['meta'] | null = null;
  series: Series = simulate(this.params, this.modelParams);
  tl: Timeline = { t: 0, t1: 0, t2: this.series.D, playing: false, speed: 2 };   // waits for the user to press play
  presets: Preset[] = [];
  points: TestPoint[] = [];               // simulatable test points (real and seed), for the map and evidence
  pointByCode = new Map<string, TestPoint>();
  version = 0;
  /* server reconciliation (SPEC §10): 'ok' = the server agrees, 'reconciled' = the server's series replaced ours */
  server: 'pending' | 'ok' | 'reconciled' | 'offline' = 'pending';
  private simTimer: ReturnType<typeof setTimeout> | undefined;
  private simSeq = 0;
  private listeners = new Set<() => void>();
  private tickListeners = new Set<() => void>();

  subscribe = (fn: () => void) => { this.listeners.add(fn); return () => { this.listeners.delete(fn); }; };
  getVersion = () => this.version;
  onTick(fn: () => void) { this.tickListeners.add(fn); return () => { this.tickListeners.delete(fn); }; }
  emit() { this.version++; this.listeners.forEach(f => f()); this.tickListeners.forEach(f => f()); }

  setPoints(points: TestPoint[]) { this.points = points; this.pointByCode = new Map(points.map(p => [p.code, p])); this.emit(); }
  setPresets(presets: Preset[]) { this.presets = presets; this.emit(); }
  setModelParams(r: ModelParamsResponse) { this.modelParams = r.params; this.paramsMeta = r.meta; this.recompute(false); }

  /* prototype onParams(): recompute, keep the window end pinned to the end of the burn, restart if asked */
  set(patch: Partial<SimParams>, restart = false) {
    Object.assign(this.params, patch);
    this.recompute(restart);
  }

  private recompute(restart: boolean) {
    const tl = this.tl;
    const wasEnd = tl.t2 >= this.series.D - 1e-6;
    this.series = simulate(this.params, this.modelParams);
    if (wasEnd) tl.t2 = this.series.D;
    tl.t2 = Math.min(tl.t2, this.series.D); tl.t1 = Math.min(tl.t1, tl.t2 - 0.5);
    if (tl.t1 < 0) tl.t1 = 0;
    // A new setting rewinds to t1 (or a finished run does); it never starts playing by itself.
    if (restart || (!tl.playing && tl.t >= tl.t2 - 1e-3)) tl.t = tl.t1;
    tl.t = Math.min(tl.t, this.series.D);
    this.emit();
    this.scheduleServer();
  }

  /* Debounced 150 ms: the server runs the same model and is the reference. If it disagrees (for example
     after `ingest fit` changed the parameters), its series replaces the client's. */
  private scheduleServer() {
    clearTimeout(this.simTimer);
    this.server = 'pending';
    this.simTimer = setTimeout(() => { void this.reconcile(); }, 150);
  }

  private async reconcile() {
    const seq = ++this.simSeq;
    const p = { ...this.params };
    try {
      const r = await api.simulate(p);
      if (seq !== this.simSeq) return;
      const c = this.series;
      const same = r.result.burns === c.r.burns && Math.abs(r.result.spread - c.r.spread) < 1e-6 && r.D === c.D;
      if (!same) {
        this.series = { r: r.result, D: r.D, n: r.n, I: Float32Array.from(r.I), X: Float32Array.from(r.x_mm), tOut: r.t_out, tEnd: r.t_end };
        this.tl.t2 = Math.min(this.tl.t2, r.D); this.tl.t = Math.min(this.tl.t, r.D);
      }
      this.server = same ? 'ok' : 'reconciled';
    } catch {
      if (seq === this.simSeq) this.server = 'offline';
    }
    this.emit();
  }

  applyPreset(p: Preset) { this.set({ g: p.g, o2: p.o2, p: p.psi, u: p.u, preset: p.key, compare: null }, true); }

  /* prototype loadRecord(): settings from a measured test. A test with no pressure in its table runs at 14.7 psi. */
  load(code: string) {
    const r = this.pointByCode.get(code);
    if (!r || r.o2_pct == null) return false;
    this.set({ g: r.gravity_g ?? 0, o2: r.o2_pct, p: r.pressure_kpa ? +(r.pressure_kpa / 6.89476).toFixed(1) : 14.7,
               u: r.flow_cm_s || 0, mat: r.material as Material, preset: 'custom', compare: code }, true);
    return true;
  }

  togglePlay() {
    const tl = this.tl;
    if (!tl.playing && (tl.t >= tl.t2 - 1e-3 || tl.t < tl.t1)) tl.t = tl.t1;
    tl.playing = !tl.playing; this.emit();
  }
  setSpeed(s: number) { this.tl.speed = s; this.emit(); }
  setWindow(t1: number, t2: number) { this.tl.t1 = t1; this.tl.t2 = t2; this.emit(); }
  seek(t: number) { this.tl.t = t; this.tl.playing = false; this.emit(); }

  advance(dt: number) {
    const tl = this.tl;
    if (!tl.playing) return;
    tl.t += dt * tl.speed;
    if (tl.t >= tl.t2) { tl.t = tl.t2; tl.playing = false; this.emit(); return; }
    this.tickListeners.forEach(f => f());
  }
}

export const sim = new SimStore();

export function useSim() {
  useSyncExternalStore(sim.subscribe, sim.getVersion);
  return sim;
}
