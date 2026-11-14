/* Landing background: air streaming around a spherical microgravity flame (potential flow past a cylinder).
   A few hundred line segments on one 2D canvas: no library, paused when hidden, one still frame under
   prefers-reduced-motion. Decorative only. */
import { useEffect, useRef } from 'react';

interface P { x: number; y: number; v: number; a: number }

export function HeroField() {
  const host = useRef<HTMLDivElement>(null);
  const cv = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const el = host.current!, c = cv.current!, ctx = c.getContext('2d');
    if (!ctx) return;
    const reduced = !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    let W = 0, H = 0, cx = 0, cy = 0, R = 0, raf = 0, last = performance.now();
    const spawn = (anywhere: boolean): P => ({ x: anywhere ? Math.random() * W : -30 - Math.random() * 60, y: Math.random() * H, v: 28 + Math.random() * 46, a: 0.10 + Math.random() * 0.30 });
    let ps: P[] = [];

    function size() {
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      W = el.clientWidth; H = el.clientHeight;
      c.width = Math.round(W * dpr); c.height = Math.round(H * dpr);
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
      const wide = W > 900;
      R = Math.min(W, H) * (wide ? 0.17 : 0.13);
      cx = wide ? W * 0.74 : W * 0.5; cy = wide ? H * 0.48 : H * 0.84;
      el.style.setProperty('--fx', cx + 'px'); el.style.setProperty('--fy', cy + 'px'); el.style.setProperty('--fr', R + 'px');
      const n = Math.round(Math.min(320, (W * H) / 5200));
      ps = Array.from({ length: n }, () => spawn(true));
    }

    function draw(dt: number, tail: number) {
      ctx!.clearRect(0, 0, W, H);
      ctx!.lineWidth = 1;
      for (const p of ps) {
        const dx = p.x - cx, dy = p.y - cy, r2 = dx * dx + dy * dy;
        let ux = 1, uy = 0;
        if (r2 > R * R * 0.9) { const k = (R * R) / (r2 * r2); ux = 1 - k * (dx * dx - dy * dy); uy = -2 * k * dx * dy; }
        const nx = p.x + ux * p.v * dt, ny = p.y + uy * p.v * dt;
        ctx!.strokeStyle = `rgba(178,198,236,${p.a})`;
        ctx!.beginPath(); ctx!.moveTo(p.x - ux * p.v * tail, p.y - uy * p.v * tail); ctx!.lineTo(nx, ny); ctx!.stroke();
        p.x = nx; p.y = ny;
        if (p.x > W + 30 || r2 < R * R * 0.8) Object.assign(p, spawn(false));
      }
    }

    const loop = (now: number) => {
      const dt = Math.min(0.05, (now - last) / 1000); last = now;
      draw(dt, 0.14);
      raf = requestAnimationFrame(loop);
    };
    size();
    if (reduced) draw(0, 0.3);
    else raf = requestAnimationFrame(loop);
    const onResize = () => { size(); if (reduced) draw(0, 0.3); };
    window.addEventListener('resize', onResize);
    return () => { cancelAnimationFrame(raf); window.removeEventListener('resize', onResize); };
  }, []);

  return (
    <div className="hero-field" ref={host} aria-hidden="true">
      <canvas ref={cv} />
      <div className="flameball"><i /></div>
    </div>
  );
}
