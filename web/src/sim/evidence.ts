/* SPEC §8.3 coverage message and nearest evidence. Thresholds come from the loaded test points, not constants:
   "extrapolated" above the highest solid-fuel O₂ with a known outcome, or below the lowest tested pressure. */
import type { TestPoint } from '../types';
import { fitLabel, PSI_TO_KPA, recDist, type SimState } from './model';

export interface Coverage { kind: 'partial-g' | 'o2' | 'pressure' | 'inside'; text: string }

export function coverage(s: SimState, points: TestPoint[]): Coverage {
  if (s.g > 0.02 && s.g < 0.95) return { kind: 'partial-g', text: 'No partial-gravity data exists yet. This sits between the 0 g and 1 g results.' };
  const o2s = points.map(p => p.o2_pct).filter((v): v is number => v != null);
  const maxO2 = o2s.length ? Math.max(...o2s) : 21;
  if (s.o2 > maxO2 + 0.5) return { kind: 'o2', text: `Extrapolated: no solid-fuel test above ${+maxO2.toFixed(1)}% O₂ in this dataset.` };
  const kpas = points.map(p => p.pressure_kpa).filter((v): v is number => v != null);
  const minKpa = kpas.length ? Math.min(...kpas) : 101.3;
  if (s.p * PSI_TO_KPA < minKpa - 5) return { kind: 'pressure', text: 'Extrapolated: no reduced-pressure solid-fuel tests in this dataset.' };
  return { kind: 'inside', text: 'Inside the range of tested conditions.' };
}

export function nearest(s: SimState, points: TestPoint[]): { point: TestPoint; d: number; fit: string } | null {
  let best: TestPoint | null = null, bd = Infinity;
  for (const p of points) { const d = recDist(p, s); if (d < bd) { bd = d; best = p; } }
  return best ? { point: best, d: bd, fit: fitLabel(bd) } : null;
}
