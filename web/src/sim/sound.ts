/* Fire sound, synthesized live with Web Audio (no audio files): a low roar of filtered brown noise whose loudness and
   brightness follow the flame's intensity, plus random crackles whose rate follows it too. It is silent until the user
   presses play (browsers only allow sound after a gesture), plays only while the timeline runs, and a toggle mutes it.
   The choice is remembered in this browser. Decorative: nothing in the sound is data. */
const KEY = 'ember-sound';

function remembered(): boolean {
  try { return localStorage.getItem(KEY) !== 'off'; } catch { return true; }
}

class FireSound {
  enabled = remembered();
  private ctx: AudioContext | null = null;
  private master: GainNode | null = null;
  private roar: GainNode | null = null;
  private tone: BiquadFilterNode | null = null;
  private white: AudioBuffer | null = null;
  private nextCrackle = 0;
  private listeners = new Set<() => void>();

  onChange(fn: () => void) { this.listeners.add(fn); return () => { this.listeners.delete(fn); }; }

  private build(): boolean {
    if (this.ctx) return true;
    const AC = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AC) return false;
    const ctx = new AC(), rate = ctx.sampleRate, len = rate * 2;
    const white = ctx.createBuffer(1, len, rate), brown = ctx.createBuffer(1, len, rate);
    const w = white.getChannelData(0), b = brown.getChannelData(0);
    let last = 0;
    for (let i = 0; i < len; i++) {
      w[i] = Math.random() * 2 - 1;
      last = (last + 0.02 * w[i]) / 1.02;            // integrated noise: a soft rumble
      b[i] = last * 3.5;
    }
    const master = ctx.createGain(); master.gain.value = 0.9; master.connect(ctx.destination);
    const roar = ctx.createGain(); roar.gain.value = 0;
    const tone = ctx.createBiquadFilter(); tone.type = 'lowpass'; tone.frequency.value = 400; tone.Q.value = 0.7;
    const src = ctx.createBufferSource(); src.buffer = brown; src.loop = true;
    src.connect(tone).connect(roar).connect(master); src.start();
    Object.assign(this, { ctx, master, roar, tone, white });
    return true;
  }

  /* Call from a click (play, ignite, the sound toggle): creates or resumes the audio context. */
  unlock() {
    if (!this.enabled || !this.build()) return;
    void this.ctx!.resume();
  }

  toggle() {
    this.enabled = !this.enabled;
    try { localStorage.setItem(KEY, this.enabled ? 'on' : 'off'); } catch { /* private mode */ }
    if (this.enabled) this.unlock(); else this.silence();
    this.listeners.forEach(f => f());
  }

  silence() {
    if (!this.ctx || !this.roar) return;
    this.roar.gain.setTargetAtTime(0, this.ctx.currentTime, 0.05);
  }

  /* Every animation frame: intensity I (0–1) of the flame now, and whether the timeline is running. */
  update(I: number, playing: boolean) {
    const ctx = this.ctx;
    if (!ctx || !this.roar || !this.tone || ctx.state !== 'running') return;
    const now = ctx.currentTime, live = this.enabled && playing && I > 0.03;
    const flicker = 0.85 + 0.3 * Math.random();
    this.roar.gain.setTargetAtTime(live ? 0.16 * I * flicker : 0, now, live ? 0.06 : 0.12);
    this.tone.frequency.setTargetAtTime(260 + 900 * I, now, 0.1);
    if (!live) { this.nextCrackle = now; return; }
    if (this.nextCrackle < now) this.nextCrackle = now;
    const rate = 3 + 16 * I;                         // crackles per second
    while (this.nextCrackle < now + 0.12) {
      this.crackle(this.nextCrackle, I);
      this.nextCrackle += -Math.log(1 - Math.random()) / rate;
    }
  }

  private crackle(t: number, I: number) {
    const ctx = this.ctx!, src = ctx.createBufferSource(), bp = ctx.createBiquadFilter(), g = ctx.createGain();
    src.buffer = this.white;
    bp.type = 'bandpass'; bp.frequency.value = 1400 + Math.random() * 4200; bp.Q.value = 0.9 + Math.random() * 2;
    const amp = (0.05 + 0.22 * Math.random() ** 2) * (0.4 + 0.6 * I), dur = 0.01 + Math.random() * 0.05;
    g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(amp, t + 0.002); g.gain.exponentialRampToValueAtTime(0.0005, t + dur);
    src.connect(bp).connect(g).connect(this.master!);
    src.start(t, Math.random() * 1.8, dur + 0.02);
  }
}

export const fireSound = new FireSound();
