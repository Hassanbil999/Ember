/* The browser's model copy must match the server's (backend/sim/model.py) on 600 golden cases,
   and pass the SPEC §8.5 anchors on its own. */
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { DEFAULT_PARAMS, model, simulate, type SimState } from './model';

const golden = JSON.parse(readFileSync(new URL('../../../backend/tests/fixtures/model_golden.json', import.meta.url), 'utf-8')) as
  { in: SimState; xlim: number; spread: number; burns: boolean; regime: string; D: number; t_out: number | null; t_end: number | null; x_last: number }[];

describe('model parity with the server', () => {
  it('has 600 cases', () => expect(golden.length).toBe(600));
  it('matches limit, outcome, spread and timing on every case', () => {
    for (const c of golden) {
      const r = model(c.in, DEFAULT_PARAMS), s = simulate(c.in, DEFAULT_PARAMS);
      expect(r.burns, JSON.stringify(c.in)).toBe(c.burns);
      expect(r.regime).toBe(c.regime);
      expect(r.xlim).toBeCloseTo(c.xlim, 9);
      expect(r.spread).toBeCloseTo(c.spread, 9);
      expect(s.D).toBe(c.D);
      if (c.t_out == null) expect(s.tOut).toBeNull(); else expect(s.tOut!).toBeCloseTo(c.t_out, 9);
      if (c.t_end == null) expect(s.tEnd).toBeNull(); else expect(s.tEnd!).toBeCloseTo(c.t_end, 9);
      expect(s.X[s.n - 1]).toBeCloseTo(c.x_last, 3);
    }
  });
});

describe('SPEC §8.5 anchors in the browser copy', () => {
  const P = DEFAULT_PARAMS;
  it('PMMA 0 g 17% 5 cm/s burns', () => expect(model({ g: 0, o2: 17, p: 14.7, u: 5, mat: 'pmma' }, P).burns).toBe(true));
  it('PMMA 0 g 21% 0.5 cm/s goes out', () => expect(model({ g: 0, o2: 21, p: 14.7, u: 0.5, mat: 'pmma' }, P).burns).toBe(false));
  it('PMMA 1 g still air: 18% out, 21% burns', () => {
    expect(model({ g: 1, o2: 18, p: 14.7, u: 0, mat: 'pmma' }, P).burns).toBe(false);
    expect(model({ g: 1, o2: 21, p: 14.7, u: 0, mat: 'pmma' }, P).burns).toBe(true);
  });
  it('fabric 0 g 21% 20 cm/s spreads 1.8 ± 0.15 mm/s', () => expect(Math.abs(model({ g: 0, o2: 21, p: 14.7, u: 20, mat: 'fabric' }, P).spread - 1.8)).toBeLessThan(0.15));
  it('fabric lunar rover, fan off burns', () => expect(model({ g: 0.166, o2: 34, p: 8.2, u: 0, mat: 'fabric' }, P).burns).toBe(true));
});
