/* Fire map (/engine/map): every NASA fire test with a known ending, as dots in 3D: oxygen across, pressure up, one lane
   per fuel in depth. Filled orange = the flame kept burning, hollow blue = it went out. Future studies: gold rings where
   the models would learn most from one more test (per fuel), and the Moon & Mars base air as a gold rod through every
   fuel lane (dashed where that air is outside what NASA tested). Drag to turn, scroll to zoom. The only filters are the
   two outcomes and future studies. Data: GET /api/fire-check/map. README Decision BB. */
import { useEffect, useMemo, useRef, useState } from 'react';
import { api, type FireMapAll, type MapCrew, type MapLane, type MapNext, type MapTest } from '../api';
import { Link } from '../router';

interface Cam { yaw: number; pitch: number; zoom: number }
type Hit = { x: number; y: number; r: number; kind: 'test'; t: MapTest } | { x: number; y: number; r: number; kind: 'next'; t: MapNext } | { x: number; y: number; r: number; kind: 'crew'; c: MapCrew; lane: MapLane };
type Sel = Exclude<Hit, { kind: 'crew' }> | { kind: 'crew'; c: MapCrew; lane: MapLane };

const HOME: Cam = { yaw: -0.55, pitch: 0.38, zoom: 1 };
const LIT = '#e0802e', OUT = '#4f97ec', GOLD = '#ffc24b';    // outcome pair validated on the dark surface (README Decision BB)
const O0 = 10, O1 = 42, PMAX = 46;
const reduced = () => typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
const X = (o2: number) => ((o2 - (O0 + O1) / 2) / ((O1 - O0) / 2)) * 1.25;
const Y = (psi: number) => (psi / PMAX) * 1.5;
const pct = (p: number) => `${Math.round(p * 100)} %`;
const nice = (v: number) => String(+v.toFixed(Math.abs(v) >= 10 ? 1 : 2));

function laneZ(lanes: MapLane[]) {
  const gas = lanes.filter(l => l.problem === 'gas').length, total = lanes.length - 1 + 0.9;
  return (l: MapLane) => ((l.lane + (l.lane >= gas ? 0.9 : 0)) / total) * 1.9 - 0.95;
}

/* Camera: turn (yaw), tilt (pitch, > 0 looks down from above), mild perspective. The scale comes from the box's
   bounding sphere, so the map keeps its size while it turns, centred in the space below the title and filters. */
function projector(cam: Cam, w: number, h: number) {
  const cy = Math.cos(cam.yaw), sy = Math.sin(cam.yaw), cp = Math.cos(cam.pitch), sp = Math.sin(cam.pitch);
  const top = w > 700 ? 215 : 200, bottom = 46, left = w > 700 ? 24 : 80, right = w > 700 ? 150 : 56;
  const W = Math.max(120, w - left - right), H = Math.max(120, h - top - bottom);
  const sc = (Math.min(W, H) / (2 * 1.72)) * (w > 700 ? 1.38 : 1.2) * cam.zoom, cx = left + W / 2, cyy = top + H * 0.4;
  return (x: number, y: number, z: number) => {
    const yy = y - 0.75;
    const x1 = x * cy + z * sy, z1 = -x * sy + z * cy;
    const y2 = yy * cp + z1 * sp, z2 = -yy * sp + z1 * cp;     // z2 > 0 is farther
    const s = 9 / (9 + z2);                                       // mild perspective, so the axes stay readable
    return { x: cx + x1 * s * sc, y: cyy - y2 * s * sc, z: z2, s };
  };
}

export function FireMap() {
  const [d, setD] = useState<FireMapAll | null>(null);
  const [err, setErr] = useState('');
  const [show, setShow] = useState({ lit: true, out: true, future: true });
  const [sel, setSel] = useState<Sel | null>(null);
  const [tip, setTip] = useState<{ x: number; y: number; lines: string[] } | null>(null);
  const [table, setTable] = useState(false);
  const [size, setSize] = useState({ w: 0, h: 0 });
  const stageRef = useRef<HTMLDivElement>(null), cvRef = useRef<HTMLCanvasElement>(null);
  const cam = useRef<Cam>({ ...HOME }), spin = useRef(!reduced()), hits = useRef<Hit[]>([]), dirty = useRef(true);
  const showRef = useRef(show), selRef = useRef(sel);
  showRef.current = show; selRef.current = sel;

  useEffect(() => { api.fireMap().then(setD).catch(e => setErr(String(e.message || e))); }, []);
  useEffect(() => {
    const el = stageRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setSize({ w: el.clientWidth, h: el.clientHeight }));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  useEffect(() => { dirty.current = true; }, [show, sel]);

  const lanes = d?.lanes ?? [];
  const Z = useMemo(() => laneZ(lanes), [lanes]);
  const counts = useMemo(() => d ? { lit: d.tests.filter(t => t.lit).length, out: d.tests.filter(t => !t.lit).length,
    future: d.next.length + d.crew.filter(c => c.needed).length } : null, [d]);

  // the render loop: redraw when something changed, while turning, and for the pulsing rings
  useEffect(() => {
    const cv = cvRef.current;
    if (!cv || !d || !size.w) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    cv.width = size.w * dpr; cv.height = size.h * dpr;
    const ctx = cv.getContext('2d');
    if (!ctx) return;
    let raf = 0;
    const draw = (ms: number) => {
      const anim = !reduced();
      if (spin.current && anim) { cam.current.yaw = HOME.yaw + 0.28 * Math.sin(ms * 0.00022); dirty.current = true; }   // a gentle sway, not a full turn
      if (dirty.current || (anim && showRef.current.future)) {
        dirty.current = false;
        render(ctx, dpr, ms);
      }
      raf = requestAnimationFrame(draw);
    };
    const render = (ctx: CanvasRenderingContext2D, dpr: number, ms: number) => {
      const { w, h } = size, P = projector(cam.current, w, h), sh = showRef.current, sl = selRef.current;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      const x0 = X(O0), x1 = X(O1), ytop = Y(PMAX), zs = lanes.map(Z), zmin = Math.min(...zs) - 0.12, zmax = Math.max(...zs) + 0.12;
      const line = (a: { x: number; y: number }, b: { x: number; y: number }) => { ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke(); };
      const text = (s: string, p: { x: number; y: number }, align: CanvasTextAlign = 'left', color = 'rgba(247,249,254,.7)', font = '12px "IBM Plex Sans", system-ui, sans-serif') => {
        ctx.font = font; ctx.fillStyle = color; ctx.textAlign = align; ctx.fillText(s, p.x, p.y);
      };
      // a box with three faint planes: the floor, and the two walls farthest from the camera
      const sans = (wgt: number, px: number) => `${wgt} ${px}px "IBM Plex Sans", system-ui, sans-serif`;
      const zFar = P(0, 0, zmax).s < P(0, 0, zmin).s ? zmax : zmin, zNear = zFar === zmax ? zmin : zmax;
      const xFar = P(x1, 0, 0).s < P(x0, 0, 0).s ? x1 : x0, xNear = xFar === x1 ? x0 : x1;
      const quad = (q: { x: number; y: number }[], fill: string) => { ctx.beginPath(); q.forEach((p, i) => (i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y))); ctx.closePath(); ctx.fillStyle = fill; ctx.fill(); };
      quad([P(x0, 0, zmin), P(x1, 0, zmin), P(x1, 0, zmax), P(x0, 0, zmax)], 'rgba(120,150,255,.06)');
      quad([P(x0, 0, zFar), P(x1, 0, zFar), P(x1, ytop, zFar), P(x0, ytop, zFar)], 'rgba(120,150,255,.035)');
      quad([P(xFar, 0, zmin), P(xFar, 0, zmax), P(xFar, ytop, zmax), P(xFar, ytop, zmin)], 'rgba(120,150,255,.035)');
      ctx.lineWidth = 1;
      ctx.strokeStyle = 'rgba(255,255,255,.08)';
      for (let o = O0; o <= O1; o += 5) { line(P(X(o), 0, zmin), P(X(o), 0, zmax)); line(P(X(o), 0, zFar), P(X(o), ytop, zFar)); }
      for (let p = 10; p <= 40; p += 10) { line(P(x0, Y(p), zFar), P(x1, Y(p), zFar)); line(P(xFar, Y(p), zmin), P(xFar, Y(p), zmax)); }
      // fuel lanes: a line on the floor, named at the near oxygen end
      lanes.forEach((l, i) => {
        ctx.strokeStyle = l.problem === 'gas' ? 'rgba(120,215,245,.35)' : 'rgba(200,170,255,.4)';
        line(P(x0, 0, zs[i]), P(x1, 0, zs[i]));
        const a = P(xNear + (xNear === x1 ? 0.07 : -0.07), 0, zs[i]);
        text(l.fuel, a, xNear === x1 ? 'left' : 'right', l.problem === 'gas' ? '#bfeefb' : '#ddd0ff', sans(600, w > 700 ? 12 : 10));
      });
      ctx.strokeStyle = 'rgba(255,255,255,.3)';
      line(P(x0, 0, zNear), P(x1, 0, zNear)); line(P(xNear, 0, zmin), P(xNear, 0, zmax)); line(P(xFar, 0, zNear), P(xFar, ytop, zNear));
      const off = zNear === zmax ? 0.13 : -0.13;
      for (let o = O0; o <= O1; o += 5) text(String(o), P(X(o), 0, zNear + off), 'center', 'rgba(247,249,254,.65)');
      for (let p = 0; p <= 40; p += 10) text(String(p), P(xFar + (xFar === x0 ? -0.05 : 0.05), Y(p), zNear), xFar === x0 ? 'right' : 'left', 'rgba(247,249,254,.65)');
      text('Oxygen, %', P(0, 0, zNear + off * 2.8), 'center', 'rgba(247,249,254,.95)', sans(600, 13));
      text('Pressure, psi', P(xFar, ytop + 0.07, zNear), 'center', 'rgba(247,249,254,.95)', sans(600, 13));
      const gasZ = zs.filter((_, i) => lanes[i].problem === 'gas'), dropZ = zs.filter((_, i) => lanes[i].problem === 'droplet');
      const grp = (zz: number[], label: string, col: string) => {
        if (!zz.length) return;
        const edge = zNear === zmax ? Math.min(...zz) - 0.2 : Math.max(...zz) + 0.2;
        text(label, P(xNear + (xNear === x1 ? 0.07 : -0.07), 0, edge), xNear === x1 ? 'left' : 'right', col, sans(700, 11));
      };
      if (w > 700) { grp(gasZ, 'GAS JETS · CFI-G', '#9fe3f8'); grp(dropZ, 'LIQUID DROPS · FLEX', '#cdb6ff'); }

      // everything with a position, drawn far to near
      const items: { z: number; draw: () => void }[] = [];
      const H: Hit[] = [];
      const laneOf = (i: number) => lanes[i];
      for (const t of d.tests) {
        if ((t.lit && !sh.lit) || (!t.lit && !sh.out)) continue;
        const p = P(X(t.o2), Y(t.psi), Z(laneOf(t.lane)));
        const r = Math.max(2.2, 3.6 * p.s * cam.current.zoom ** 0.5), on = sl?.kind === 'test' && sl.t.id === t.id;
        H.push({ x: p.x, y: p.y, r: r + 3, kind: 'test', t });
        const f = P(X(t.o2), 0, Z(laneOf(t.lane)));
        items.push({ z: p.z, draw: () => {
          ctx.strokeStyle = t.lit ? 'rgba(224,128,46,.22)' : 'rgba(79,151,236,.2)'; ctx.lineWidth = 1; line(p, f);
          ctx.beginPath(); ctx.arc(p.x, p.y, on ? r + 2 : r, 0, Math.PI * 2);
          if (t.lit) { ctx.fillStyle = LIT; ctx.fill(); ctx.strokeStyle = 'rgba(8,12,30,.9)'; ctx.lineWidth = 1; ctx.stroke(); }
          else { ctx.fillStyle = 'rgba(8,12,30,.85)'; ctx.fill(); ctx.strokeStyle = OUT; ctx.lineWidth = 1.6; ctx.stroke(); }
          if (on) { ctx.beginPath(); ctx.arc(p.x, p.y, r + 6, 0, Math.PI * 2); ctx.strokeStyle = '#fff'; ctx.lineWidth = 1.5; ctx.stroke(); }
        } });
      }
      // crew air: a rod through every fuel lane; ISS for reference, the Moon & Mars base as a future study
      for (const c of d.crew) {
        if (c.needed && !sh.future) continue;
        const col = c.needed ? GOLD : 'rgba(255,255,255,.75)';
        lanes.forEach((l, i) => {
          const a = P(X(c.o2), Y(c.psi), zs[i] - 0.13), b = P(X(c.o2), Y(c.psi), zs[i] + 0.13), m = P(X(c.o2), Y(c.psi), zs[i]);
          const untested = c.zone_by_lane[String(l.lane)] === 'untested';
          H.push({ x: m.x, y: m.y, r: 9, kind: 'crew', c, lane: l });
          items.push({ z: m.z, draw: () => {
            ctx.strokeStyle = col; ctx.lineWidth = c.needed ? 3 : 2; ctx.setLineDash(untested ? [3, 4] : []); line(a, b); ctx.setLineDash([]);
            if (c.needed && untested) { ctx.beginPath(); ctx.arc(m.x, m.y, 4 * m.s, 0, Math.PI * 2); ctx.strokeStyle = GOLD; ctx.lineWidth = 1.4; ctx.stroke(); }
          } });
        });
        const end = P(X(c.o2), Y(c.psi), zmin - 0.08);
        items.push({ z: end.z, draw: () => text(c.needed ? `${c.label}: no test at their gravity` : c.label, { x: end.x + 6, y: end.y - 6 }, 'left', c.needed ? GOLD : 'rgba(247,249,254,.85)', '600 12px "IBM Plex Sans", system-ui, sans-serif') });
      }
      // the models' next tests: pulsing gold rings
      if (sh.future) for (const n of d.next) {
        const p = P(X(n.o2), Y(n.psi), Z(laneOf(n.lane))), pulse = reduced() ? 0 : Math.sin(ms / 400 + n.o2) * 1.5;
        const r = 7 * p.s + pulse, on = sl?.kind === 'next' && sl.t === n;
        H.push({ x: p.x, y: p.y, r: r + 3, kind: 'next', t: n });
        items.push({ z: p.z - 0.001, draw: () => {
          ctx.beginPath(); ctx.arc(p.x, p.y, r, 0, Math.PI * 2); ctx.setLineDash([3, 3]); ctx.strokeStyle = GOLD; ctx.lineWidth = on ? 2.4 : 1.6; ctx.stroke(); ctx.setLineDash([]);
          ctx.fillStyle = GOLD; ctx.font = '700 10px "IBM Plex Mono", monospace'; ctx.textAlign = 'center'; ctx.fillText('?', p.x, p.y + 3.5);
        } });
      }
      items.sort((a, b) => b.z - a.z).forEach(it => it.draw());
      hits.current = H;
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [d, size, lanes, Z]);

  // turning and zooming
  const drag = useRef<{ x: number; y: number; cam: Cam; moved: boolean } | null>(null);
  useEffect(() => {
    const cv = cvRef.current;
    if (!cv) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault(); spin.current = false;
      cam.current.zoom = Math.min(2.6, Math.max(0.55, cam.current.zoom * (e.deltaY > 0 ? 0.9 : 1.1))); dirty.current = true;
    };
    cv.addEventListener('wheel', onWheel, { passive: false });
    return () => cv.removeEventListener('wheel', onWheel);
  }, [d]);
  const pick = (x: number, y: number): Hit | null => {
    let best: Hit | null = null, bd = 1e9;
    for (const h of hits.current) { const dd = Math.hypot(h.x - x, h.y - y); if (dd <= h.r && dd < bd) { best = h; bd = dd; } }
    return best;
  };
  const describe = (h: Hit): string[] => {
    if (h.kind === 'test') { const l = lanes[h.t.lane]; return [`${h.t.id} · ${l.fuel}`, `${h.t.lit ? l.outcome_yes : l.outcome_no}`, `${nice(h.t.o2)} % O₂ · ${nice(h.t.psi)} psi · ${d!.size_label[l.problem]} ${h.t.size} ${d!.size_unit[l.problem]}${h.t.co2 ? ` · CO₂ ${h.t.co2} %` : ''}${h.t.he ? ` · He ${h.t.he} %` : ''}`]; }
    if (h.kind === 'next') { const l = lanes[h.t.lane]; return [`Test next · ${l.fuel}`, `${nice(h.t.o2)} % O₂ · ${nice(h.t.psi)} psi`, `models range ${pct(h.t.low)}–${pct(h.t.high)}: one test here teaches them most`]; }
    const z = h.c.zone_by_lane[String(h.lane.lane)];
    return [`${h.c.label} · ${h.lane.fuel}`, `${h.c.o2} % O₂ · ${h.c.psi} psi`, z === 'untested' ? 'Outside what NASA tested for this fuel' : `In microgravity: ${z} by NASA tests of this fuel`];
  };
  function onDown(e: React.PointerEvent<HTMLCanvasElement>) { drag.current = { x: e.clientX, y: e.clientY, cam: { ...cam.current }, moved: false }; e.currentTarget.setPointerCapture(e.pointerId); }
  function onMove(e: React.PointerEvent<HTMLCanvasElement>) {
    const r = e.currentTarget.getBoundingClientRect(), g = drag.current;
    if (g) {
      const dx = e.clientX - g.x, dy = e.clientY - g.y;
      if (Math.abs(dx) + Math.abs(dy) > 4) g.moved = true;
      if (g.moved) {
        spin.current = false;
        cam.current.yaw = g.cam.yaw + dx * 0.008;
        cam.current.pitch = Math.min(1.35, Math.max(-0.1, g.cam.pitch + dy * 0.006));
        dirty.current = true; setTip(null); return;
      }
    }
    const h = pick(e.clientX - r.left, e.clientY - r.top);
    setTip(h ? { x: e.clientX, y: e.clientY, lines: describe(h) } : null);
    e.currentTarget.style.cursor = h ? 'pointer' : 'grab';
  }
  function onUp(e: React.PointerEvent<HTMLCanvasElement>) {
    const g = drag.current;
    drag.current = null;
    if (g && !g.moved) {
      const r = e.currentTarget.getBoundingClientRect(), h = pick(e.clientX - r.left, e.clientY - r.top);
      setSel(h); spin.current = false;
    }
  }
  function onKey(e: React.KeyboardEvent) {
    const k: Record<string, () => void> = {
      ArrowLeft: () => { cam.current.yaw -= 0.12; }, ArrowRight: () => { cam.current.yaw += 0.12; },
      ArrowUp: () => { cam.current.pitch = Math.min(1.35, cam.current.pitch + 0.1); }, ArrowDown: () => { cam.current.pitch = Math.max(-0.1, cam.current.pitch - 0.1); },
      '+': () => { cam.current.zoom = Math.min(2.6, cam.current.zoom * 1.15); }, '=': () => { cam.current.zoom = Math.min(2.6, cam.current.zoom * 1.15); },
      '-': () => { cam.current.zoom = Math.max(0.55, cam.current.zoom / 1.15); }, '0': () => { cam.current = { ...HOME }; },
    };
    if (k[e.key]) { e.preventDefault(); spin.current = false; k[e.key](); dirty.current = true; }
  }

  const label = d ? `3D map of ${d.tests.length} NASA fire tests: oxygen across, pressure up, ${lanes.length} fuels in depth. ${counts!.lit} kept burning, ${counts!.out} went out; ${d.next.length} suggested next tests. Arrow keys turn it, plus and minus zoom, 0 resets.` : 'Fire map';

  return (
    <section id="view-map" className="view fmap" aria-labelledby="fmTitle">
      <div className="fm-stage" ref={stageRef}>
        <canvas ref={cvRef} id="fmCanvas" className="fm-cv" tabIndex={0} role="img" aria-label={label}
          onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerLeave={() => setTip(null)} onKeyDown={onKey} />
        <div className="fm-top">
          <h2 id="fmTitle">Fire map</h2>
          <p>Every NASA fire test with a known ending, by oxygen, pressure and fuel. Drag to turn.</p>
          {d && counts && (
            <div className="fm-filters" role="group" aria-label="Show">
              <button type="button" id="fm-lit" className="fm-chip" aria-pressed={show.lit} onClick={() => setShow(s => ({ ...s, lit: !s.lit }))}><i className="dot lit" />Kept burning <b className="num">{counts.lit}</b></button>
              <button type="button" id="fm-out" className="fm-chip" aria-pressed={show.out} onClick={() => setShow(s => ({ ...s, out: !s.out }))}><i className="dot out" />Went out <b className="num">{counts.out}</b></button>
              <button type="button" id="fm-future" className="fm-chip" aria-pressed={show.future} onClick={() => setShow(s => ({ ...s, future: !s.future }))}><i className="dot next" />Future studies <b className="num">{counts.future}</b></button>
            </div>
          )}
        </div>
        <button type="button" className="fm-reset" onClick={() => { cam.current = { ...HOME }; spin.current = !reduced(); dirty.current = true; }} aria-label="Reset the view">↺</button>
        {sel && d && <Details s={sel} d={d} onClose={() => setSel(null)} />}
        {d && (
          <p className="fm-foot">{d.tests.length} tests · {[...new Set(lanes.map(l => `${l.investigation} (${l.psi_id})`))].join(' · ')} · the NASA tables give no airflow for these tests ·{' '}
            <button type="button" className="linkbtn" id="fmTableBtn" aria-expanded={table} onClick={() => setTable(t => !t)}>{table ? 'Hide the table' : 'Show as a table'}</button></p>
        )}
        {table && d && <MapTable d={d} />}
        {err && <p className="err fm-err" role="alert">Could not load the map ({err}).</p>}
        {!d && !err && <p className="loading fm-err">Loading the map…</p>}
      </div>
      {tip && <div className="tooltip" style={{ left: tip.x + 14, top: tip.y + 14 }}>{tip.lines.map(l => <div key={l}>{l}</div>)}</div>}
    </section>
  );
}

function checkLink(l: MapLane, o2: number, psi: number, size: number | null, co2 = 0, he = 0) {
  const q = new URLSearchParams({ problem: l.problem, fuel: l.fuel, o2: String(o2), psi: String(psi), g: '0' });
  if (l.problem === 'gas') q.set('flow', String(size ?? 1)); else { q.set('d0', String(size ?? 3)); if (co2) q.set('co2', String(co2)); if (he) q.set('he', String(he)); }
  return '/engine/check?' + q.toString();
}

function Details({ s, d, onClose }: { s: Sel; d: FireMapAll; onClose: () => void }) {
  const l = s.kind === 'crew' ? s.lane : d.lanes[s.t.lane];
  return (
    <aside className="fm-card" id="fmDetails" aria-live="polite">
      <button type="button" className="fm-x" onClick={onClose} aria-label="Close">×</button>
      {s.kind === 'test' && <>
        <span className={'fm-tag ' + (s.t.lit ? 'lit' : 'out')}>{s.t.lit ? l.outcome_yes : l.outcome_no}</span>
        <h3>{s.t.id}</h3>
        <p>{l.kind} · {l.fuel} · {l.investigation} ({l.psi_id}) · {s.t.campaign}</p>
        <p className="num">{nice(s.t.o2)} % O₂ · {nice(s.t.psi)} psi · {d.size_label[l.problem]} {s.t.size} {d.size_unit[l.problem]}{s.t.co2 ? ` · CO₂ ${s.t.co2} %` : ''}{s.t.he ? ` · He ${s.t.he} %` : ''}</p>
        <div className="fm-links"><Link to={`/engine/data?q=${encodeURIComponent(s.t.id)}`}>Find the NASA row →</Link><Link to={checkLink(l, s.t.o2, s.t.psi, s.t.size, s.t.co2, s.t.he)}>Fire check here →</Link></div>
      </>}
      {s.kind === 'next' && <>
        <span className="fm-tag next">Future study</span>
        <h3>Test next: {l.fuel}</h3>
        <p className="num">{nice(s.t.o2)} % O₂ · {nice(s.t.psi)} psi{s.t.size != null ? ` · ${d.size_label[l.problem]} ${s.t.size} ${d.size_unit[l.problem]}` : ''}</p>
        <p>The models disagree most here ({pct(s.t.low)}–{pct(s.t.high)} chance it {l.outcome_yes.replace(/^(stayed|burned)/, m => (m === 'stayed' ? 'stays' : 'burns'))}), so one NASA test here would teach them the most. Nearest test: {s.t.nearest}.</p>
        <div className="fm-links"><Link to={checkLink(l, s.t.o2, s.t.psi, s.t.size)}>Fire check here →</Link></div>
      </>}
      {s.kind === 'crew' && <>
        <span className={'fm-tag ' + (s.c.needed ? 'next' : 'ref')}>{s.c.needed ? 'Future study' : 'Reference'}</span>
        <h3>{s.c.label}</h3>
        <p className="num">{s.c.o2} % O₂ · {s.c.psi} psi</p>
        <p>{s.c.needed ? 'No NASA fire test has run at Moon or Mars gravity yet. ' : ''}For {l.fuel} in microgravity this air is <b>{s.c.zone_by_lane[String(l.lane)]}</b> by NASA's tests.</p>
        <div className="fm-links"><Link to={checkLink(l, s.c.o2, s.c.psi, null)}>Fire check here →</Link></div>
      </>}
    </aside>
  );
}

function MapTable({ d }: { d: FireMapAll }) {
  return (
    <div className="fm-table card" id="fmTable">
      <table>
        <caption>NASA tests with a known ending, by fuel, and where tests are needed</caption>
        <thead><tr><th scope="col">Fuel</th><th scope="col">Tests</th><th scope="col">Kept burning</th><th scope="col">Went out</th><th scope="col">Test next (O₂ %, psi)</th><th scope="col">Moon &amp; Mars air</th></tr></thead>
        <tbody>
          {d.lanes.map(l => {
            const moon = d.crew.find(c => c.needed);
            return (
              <tr key={l.lane}><th scope="row">{l.fuel} <small>({l.kind.toLowerCase()})</small></th><td className="num">{l.n}</td><td className="num">{l.lit}</td><td className="num">{l.n - l.lit}</td>
                <td className="num">{d.next.filter(n => n.lane === l.lane).map(n => `${nice(n.o2)}, ${nice(n.psi)}`).join(' · ') || '—'}</td>
                <td>{moon ? moon.zone_by_lane[String(l.lane)] : '—'}</td></tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
