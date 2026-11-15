/* The simulator stage, ported from prototype/index.html "CANVASES": particle airflow (trails canvas), duct and
   sample (scene canvas), and the WebGL flame shader with a 2D fallback. Reads the simulator store each frame. */
import { at, fmtU, IGN, SAMPLE_MM } from './model';
import { sim } from './store';

const reduced = typeof window !== 'undefined' && !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
export const isWide = () => window.innerWidth > 1100;

interface Particle { x: number; y: number; px: number; py: number; age: number; life: number; dep: number }
interface Geom { I: number; xmm: number; off: number; fx: number; fy: number; len: number; wid: number; round: number; ang: number; soot: number; turb: number; speed: number; vmag: number; ub: number }

const FS = `precision mediump float;
uniform vec2 u_res; uniform float u_dpr; uniform float u_time; uniform vec2 u_anchor;
uniform float u_angle; uniform float u_len; uniform float u_wid; uniform float u_I;
uniform float u_soot; uniform float u_turb; uniform float u_speed; uniform float u_round;
float hash(vec2 p){ p=fract(p*vec2(123.34,456.21)); p+=dot(p,p+45.32); return fract(p.x*p.y); }
float noise(vec2 p){ vec2 i=floor(p); vec2 f=fract(p); vec2 w=f*f*(3.0-2.0*f);
  return mix(mix(hash(i),hash(i+vec2(1.0,0.0)),w.x),mix(hash(i+vec2(0.0,1.0)),hash(i+vec2(1.0,1.0)),w.x),w.y); }
float fbm(vec2 p){ float v=0.0; float a=0.5; for(int i=0;i<5;i++){ v+=a*noise(p); p=p*2.02+vec2(1.7,9.2); a*=0.5; } return v; }
void main(){
  vec2 p=vec2(gl_FragCoord.x, u_res.y*u_dpr-gl_FragCoord.y)/u_dpr;
  vec2 d=p-u_anchor; float ca=cos(u_angle); float sa=sin(u_angle);
  vec2 q=vec2(ca*d.x+sa*d.y, -sa*d.x+ca*d.y);
  vec2 uv=vec2(q.x/max(u_len,1.0), q.y/max(u_wid,1.0));
  if(u_I<0.005 || uv.x<-1.6 || uv.x>3.4 || abs(uv.y)>4.5){ gl_FragColor=vec4(0.0); return; }
  float t=u_time;
  float cx=mix(0.42,0.0,u_round); float sxx=mix(0.58,0.95,u_round);
  float along=smoothstep(-0.1,1.0,uv.x);
  float taper=mix(mix(1.0,0.32,along),1.0,u_round);
  vec2 nuv=vec2(uv.x*2.4-t*u_speed, uv.y*1.7);
  float n1=fbm(nuv); float n2=fbm(nuv*2.1+vec2(4.3,-t*0.35));
  float wob=(n1-0.5)*(0.25+1.1*u_turb)*along*(1.0-u_round*0.7);
  vec2 e=vec2((uv.x-cx)/sxx, (uv.y+wob)/taper);
  float dist=length(e)+(n2-0.5)*(0.16+0.5*u_turb)*mix(along,0.5,u_round);
  float body=1.0-smoothstep(0.72,1.0,dist);
  float core=1.0-smoothstep(0.0,0.75,dist);
  float heat=clamp(body*(0.5+0.5*core),0.0,1.0)*u_I;
  vec3 hot=vec3(1.0,0.26,0.03)*smoothstep(0.0,0.35,heat)+vec3(0.0,0.44,0.13)*smoothstep(0.28,0.78,heat)+vec3(0.0,0.08,0.42)*smoothstep(0.72,1.0,heat);
  vec3 blu=vec3(0.16,0.36,1.0)*smoothstep(0.0,0.55,heat)+vec3(0.30,0.32,0.20)*smoothstep(0.65,1.0,heat);
  float lum=u_soot*smoothstep(0.05,0.65,mix(uv.x,0.6-0.6*dist,u_round))*(0.55+0.45*u_soot);
  vec3 col=mix(blu,hot,clamp(lum*1.6,0.0,1.0));
  float base=(1.0-smoothstep(-0.2,mix(0.28,0.05,u_round),uv.x))*(1.0-smoothstep(0.75,1.05,dist));
  col+=vec3(0.08,0.26,0.95)*base*0.85*u_I;
  float halo=exp(-max(dist-0.72,0.0)*4.0)*0.12*u_I;
  col+=mix(vec3(0.18,0.36,1.0),vec3(1.0,0.42,0.1),u_soot)*halo*(1.0-body*0.6);
  float a=clamp(max(col.r,max(col.g,col.b)),0.0,1.0);
  col=min(col,vec3(a));
  float s=uv.x-0.95; float sw=0.45+0.55*max(s,0.0);
  float sn=fbm(vec2(uv.x*1.6-t*u_speed*0.55, uv.y*1.4+7.0));
  float dens=smoothstep(-0.05,0.4,s)*(1.0-smoothstep(0.2*sw,sw,abs(uv.y+(sn-0.5)*0.8*sw)))*(1.0-smoothstep(1.2,2.4,s));
  dens*=(0.35+0.9*sn)*u_soot*u_I*0.55*(1.0-u_round*0.7);
  gl_FragColor=vec4(col+vec3(0.40,0.38,0.36)*dens*(1.0-a), a+dens*(1.0-a));
}`;

export class StageEngine {
  private tx: CanvasRenderingContext2D;
  private sx: CanvasRenderingContext2D;
  private gl: WebGLRenderingContext | null = null;
  private U: Record<string, WebGLUniformLocation | null> = {};
  private W = 0; private H = 0; private DPR = 1; private gdpr = 1;
  private box = { l: 0, r: 0 }; private xs0 = 0; private xs1 = 0; private ys = 0;
  private parts: Particle[] = [];
  private clock = 0;
  panelL = true; panelR = true;

  constructor(private stage: HTMLElement, private tC: HTMLCanvasElement, private sC: HTMLCanvasElement, private fC: HTMLCanvasElement) {
    this.tx = tC.getContext('2d')!;
    this.sx = sC.getContext('2d')!;
    this.initGL();
    this.resize();
    // Pre-fill the airflow trails (90 frames) without drawing the flame each time; then one full frame.
    const G = this.flameGeom();
    for (let i = 0; i < 90; i++) { this.stepParticles(1 / 60, G); this.drawTrails(); }
    this.frame(0);
  }

  get hasWebGL() { return !!this.gl; }

  layout() {
    const wide = isWide();
    const pl = wide && this.panelL ? 16 + 296 + 24 : 20;
    const pr = wide && this.panelR ? 16 + 340 + 24 : 20;
    this.box = { l: pl, r: Math.max(pl + 200, this.W - pr) };
    const bw = this.box.r - this.box.l;
    this.xs0 = this.box.l + bw * 0.1; this.xs1 = this.box.l + bw * 0.9;
    this.ys = wide ? this.H * 0.45 : this.H * 0.55;
  }

  resize() {
    const st = this.stage.getBoundingClientRect();
    this.DPR = Math.min(window.devicePixelRatio || 1, 2);
    this.W = Math.max(300, st.width); this.H = Math.max(240, st.height);
    for (const c of [this.tC, this.sC]) { c.width = Math.round(this.W * this.DPR); c.height = Math.round(this.H * this.DPR); }
    this.tx.setTransform(this.DPR, 0, 0, this.DPR, 0, 0); this.sx.setTransform(this.DPR, 0, 0, this.DPR, 0, 0);
    this.gdpr = Math.min(this.DPR, 1.5);                     // WebGL at ≤ 1.5× DPR (SPEC §12)
    this.fC.width = Math.round(this.W * this.gdpr); this.fC.height = Math.round(this.H * this.gdpr);
    if (this.gl) this.gl.viewport(0, 0, this.fC.width, this.fC.height);
    this.layout();
    const n = reduced ? 300 : Math.round(Math.min(1300, this.W * this.H / 700));   // particles scale with area, cap 1300
    this.parts = Array.from({ length: n }, () => this.spawn());
  }

  private spawn(): Particle { return { x: Math.random() * this.W, y: Math.random() * this.H, px: 0, py: 0, age: 0, life: 2 + Math.random() * 4, dep: 0 }; }

  /* Flame geometry shared by WebGL, fallback and the airflow field. */
  private flameGeom(): Geom {
    const { series, tl, params: state } = sim;
    const r = series.r, I = at(series.I, tl.t, series.n), xmm = at(series.X, tl.t, series.n);
    const g = state.g, u = state.u, ub = 30 * Math.sqrt(g), vmag = Math.hypot(u, ub), e = vmag / (vmag + 9);
    const S = (16 + Math.min(56, 3 * Math.max(r.margin, 1.2))) * (0.45 + 0.55 * Math.min(1, I * 1.2));
    const ang = vmag < 0.2 ? -Math.PI / 2 : Math.atan2(-ub, u);
    const thick = state.mat === 'pmma' ? 10 : 3;
    // The flame stays at the centre of the view; the sample is drawn shifted by `off` so its burning front sits there.
    const fx = (this.xs0 + this.xs1) / 2, off = fx - (this.xs0 + (this.xs1 - this.xs0) * xmm / SAMPLE_MM);
    const soot = Math.min(1, Math.max(0.06, 0.1 + 0.8 * Math.sqrt(g) * (0.55 + (state.o2 - 15) / 40)));
    return { I, xmm, off, fx, fy: this.ys - thick / 2, len: S * (1 + 2 * e), wid: S * (0.9 - 0.4 * e), round: 1 - e, ang, soot,
             turb: Math.min(1, 0.95 * Math.sqrt(g)) * (reduced ? 0.5 : 1), speed: (0.35 + 0.05 * vmag) * (reduced ? 0.4 : 1), vmag, ub };
  }

  private field(x: number, y: number, G: Geom): [number, number] {
    const state = sim.params;
    const Uv = state.u > 0 ? 38 * Math.sqrt(state.u) : 0;
    let vx = Uv, vy = 0;
    if (G.I > 0.02) {
      const fx = G.fx, fy = G.fy;
      const Bv = 90 * Math.sqrt(state.g) * G.I, up = fy - y;
      if (Bv > 1) {
        const shift = up > 0 ? up * Uv / Math.max(Bv, 1) * 0.6 : 0;
        const dx = x - (fx + shift), sig = 24 + 20 * G.I + Math.max(up, 0) * 0.12;
        vy -= Bv * Math.exp(-dx * dx / (2 * sig * sig)) * (up > 0 ? 1 : Math.exp(-up * up / 1568));
      }
      const ddx = x - fx, ddy = y - fy, rr = Math.sqrt(ddx * ddx + ddy * ddy) + 1;
      const pull = (10 + 0.35 * Bv) * G.I * Math.exp(-rr * rr / 14450);
      vx -= pull * ddx / rr; vy -= pull * ddy / rr;
    }
    return [vx, vy];
  }

  private stepParticles(dt: number, G: Geom) {
    const cx = G.fx + Math.cos(G.ang) * G.len * 0.35 * (1 - G.round), cy = G.fy + Math.sin(G.ang) * G.len * 0.35 * (1 - G.round);
    const rad = Math.max(G.len, G.wid) * 0.6 * G.I;
    for (const p of this.parts) {
      p.px = p.x; p.py = p.y;
      const [vx, vy] = this.field(p.x, p.y, G);
      p.x += (vx + (Math.random() - 0.5) * 14) * dt; p.y += (vy + (Math.random() - 0.5) * 14) * dt; p.age += dt;
      if (G.I > 0.15) { const dx = p.x - cx, dy = p.y - cy; if (dx * dx + dy * dy < rad * rad) p.dep = 1; }
      if (p.age > p.life || p.x < -5 || p.x > this.W + 5 || p.y < -5 || p.y > this.H + 5) { Object.assign(p, this.spawn()); p.px = p.x; p.py = p.y; }
    }
  }

  private drawTrails() {
    const tx = this.tx, W = this.W, H = this.H;
    tx.globalCompositeOperation = 'destination-out';
    tx.fillStyle = 'rgba(0,0,0,' + (reduced ? 0.3 : 0.1) + ')'; tx.fillRect(0, 0, W, H);
    tx.globalCompositeOperation = 'source-over';
    tx.lineWidth = 1.05; tx.lineCap = 'round';
    const a = 0.22 + 0.5 * (sim.params.o2 - 15) / 30;
    tx.strokeStyle = 'rgba(205,222,255,' + a.toFixed(3) + ')'; tx.beginPath();
    for (const p of this.parts) if (!p.dep) { tx.moveTo(p.px, p.py); tx.lineTo(p.x, p.y); }
    tx.stroke();
    tx.strokeStyle = 'rgba(115,122,145,.22)'; tx.beginPath();
    for (const p of this.parts) if (p.dep) { tx.moveTo(p.px, p.py); tx.lineTo(p.x, p.y); }
    tx.stroke();
  }

  private arrow(c: CanvasRenderingContext2D, x1: number, y1: number, x2: number, y2: number) {
    c.beginPath(); c.moveTo(x1, y1); c.lineTo(x2, y2); c.stroke();
    const a = Math.atan2(y2 - y1, x2 - x1);
    c.beginPath(); c.moveTo(x2, y2); c.lineTo(x2 - 7 * Math.cos(a - 0.45), y2 - 7 * Math.sin(a - 0.45)); c.lineTo(x2 - 7 * Math.cos(a + 0.45), y2 - 7 * Math.sin(a + 0.45)); c.closePath(); c.fill();
  }

  private drawScene(G: Geom) {
    const c = this.sx, W = this.W, H = this.H, ys = this.ys, box = this.box, xs0 = this.xs0, xs1 = this.xs1;
    const state = sim.params;
    c.clearRect(0, 0, W, H);
    const yT = ys - Math.min(H * 0.3, 190), yB = ys + Math.min(H * 0.22, 130);
    c.strokeStyle = 'rgba(148,158,179,.22)'; c.lineWidth = 1; c.setLineDash([5, 7]);
    c.beginPath(); c.moveTo(box.l, yT); c.lineTo(box.r, yT); c.moveTo(box.l, yB); c.lineTo(box.r, yB); c.stroke(); c.setLineDash([]);
    c.font = '13px "IBM Plex Sans", system-ui, sans-serif'; c.fillStyle = 'rgba(176,186,206,.85)'; c.strokeStyle = 'rgba(232,236,244,.8)'; c.lineWidth = 1.4;
    c.fillStyle = 'rgba(232,236,244,.8)';
    if (state.u > 0) this.arrow(c, box.l, yT + 20, box.l + 36 + Math.min(56, 10 * Math.sqrt(state.u)), yT + 20);
    c.fillStyle = 'rgba(176,186,206,.85)';
    c.fillText(state.u > 0 ? 'airflow ' + fmtU(state.u) : 'still air', box.l, yT + 38);
    const gx = box.r - 6;
    c.fillStyle = 'rgba(232,236,244,.8)';
    if (state.g > 0.01) this.arrow(c, gx, yT + 10, gx, yT + 10 + Math.max(12, 40 * Math.sqrt(state.g)));
    c.fillStyle = 'rgba(176,186,206,.85)'; c.textAlign = 'right';
    c.fillText(state.g < 0.01 ? 'no gravity' : state.g.toFixed(2) + ' g', gx - 12, yT + 22); c.textAlign = 'left';
    // sample: drawn shifted so the burning front stays under the centred flame; clipped to the view between the panels
    const thick = state.mat === 'pmma' ? 10 : 3, fx = G.fx, s0 = xs0 + G.off, s1 = xs1 + G.off;
    c.save(); c.beginPath(); c.rect(box.l, 0, box.r - box.l, H); c.clip();
    c.fillStyle = state.mat === 'pmma' ? '#2e3850' : '#c7b48c';
    c.fillRect(fx, ys - thick / 2, Math.max(0, s1 - fx), thick);
    const bt = state.mat === 'pmma' ? thick * 0.55 : thick;
    c.fillStyle = state.mat === 'pmma' ? '#151a26' : '#3e352e';
    c.fillRect(s0, ys - bt / 2, Math.max(0, fx - s0), bt);
    if (G.I > 0.02 && fx > s0) {
      const gw = Math.min(60, fx - s0);
      const gr = c.createLinearGradient(fx - gw, 0, fx, 0);
      gr.addColorStop(0, 'rgba(255,90,30,0)'); gr.addColorStop(1, 'rgba(255,110,40,' + (0.75 * G.I) + ')');
      c.fillStyle = gr; c.fillRect(fx - gw, ys - bt / 2 - 0.5, gw, bt + 1);
    }
    c.fillStyle = 'rgba(148,158,179,.55)'; c.fillRect(s0 - 4, ys - 12, 2, 24); c.fillRect(s1 + 2, ys - 12, 2, 24);
    const t = sim.tl.t;
    if (t < IGN) { const a = 1 - t / IGN; c.strokeStyle = 'rgba(255,120,60,' + a + ')'; c.lineWidth = 2.5; c.beginPath(); c.moveTo(s0 + 2, ys - 11); c.lineTo(s0 + 8, ys + 11); c.stroke(); }
    c.restore();
    c.fillStyle = 'rgba(148,158,179,.7)'; c.textAlign = 'center';
    c.fillText(G.xmm.toFixed(0) + ' of 100 mm burned', fx, ys + 30); c.textAlign = 'left';
    if (!this.gl && G.I > 0.02) this.drawFlame2D(c, G);
  }

  private drawFlame2D(c: CanvasRenderingContext2D, G: Geom) {
    const outer = [Math.round(90 + 165 * G.soot), Math.round(150 + 20 * G.soot), Math.round(255 - 185 * G.soot)];
    c.save(); c.globalCompositeOperation = 'lighter';
    c.translate(G.fx, G.fy); c.rotate(G.ang); c.translate(G.len * 0.42 * (1 - G.round), 0); c.scale(1, G.wid / G.len);
    const gr = c.createRadialGradient(0, 0, 0, 0, 0, G.len * 0.6);
    gr.addColorStop(0, 'rgba(255,244,225,' + (0.25 + 0.6 * G.soot) * G.I + ')'); gr.addColorStop(0.4, 'rgba(' + outer + ',' + 0.7 * G.I + ')'); gr.addColorStop(1, 'rgba(' + outer + ',0)');
    c.fillStyle = gr; c.beginPath(); c.arc(0, 0, G.len * 0.6, 0, Math.PI * 2); c.fill(); c.restore();
  }

  private initGL() {
    let gl: WebGLRenderingContext | null = null;
    try { gl = this.fC.getContext('webgl', { premultipliedAlpha: true, alpha: true, antialias: false }); } catch { gl = null; }
    if (!gl) return;
    const vs = 'attribute vec2 a;void main(){gl_Position=vec4(a,0.0,1.0);}';
    const sh = (type: number, src: string) => { const s = gl!.createShader(type)!; gl!.shaderSource(s, src); gl!.compileShader(s); return gl!.getShaderParameter(s, gl!.COMPILE_STATUS) ? s : null; };
    const v = sh(gl.VERTEX_SHADER, vs), f = sh(gl.FRAGMENT_SHADER, FS);
    if (!v || !f) return;
    const pr = gl.createProgram()!; gl.attachShader(pr, v); gl.attachShader(pr, f); gl.linkProgram(pr);
    if (!gl.getProgramParameter(pr, gl.LINK_STATUS)) return;
    gl.useProgram(pr);
    const b = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, b); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(pr, 'a'); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    for (const n of ['res', 'dpr', 'time', 'anchor', 'angle', 'len', 'wid', 'I', 'soot', 'turb', 'speed', 'round']) this.U[n] = gl.getUniformLocation(pr, 'u_' + n);
    this.gl = gl;
  }

  private drawFlameGL(G: Geom) {
    const gl = this.gl, U = this.U;
    if (!gl) return;
    gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
    if (G.I < 0.01) return;
    gl.uniform2f(U.res, this.W, this.H); gl.uniform1f(U.dpr, this.gdpr); gl.uniform1f(U.time, this.clock % 1000);
    gl.uniform2f(U.anchor, G.fx, G.fy); gl.uniform1f(U.angle, G.ang); gl.uniform1f(U.len, G.len); gl.uniform1f(U.wid, G.wid);
    gl.uniform1f(U.I, G.I); gl.uniform1f(U.soot, G.soot); gl.uniform1f(U.turb, G.turb); gl.uniform1f(U.speed, G.speed); gl.uniform1f(U.round, G.round);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }

  frame(dt: number) {
    this.clock += dt;
    const G = this.flameGeom();
    this.stepParticles(dt, G); this.drawTrails(); this.drawScene(G); this.drawFlameGL(G);
  }
}
