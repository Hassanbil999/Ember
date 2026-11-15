/* Presentation (/presentation, /presentation/3): an in-app deck. Arrow keys, Page Up/Down and the buttons move;
   the slide number is in the URL; Fullscreen and Print (one slide per page) are built in. Live numbers come from
   the engine. Text marked "draft" is for the team to write or check. */
import { useEffect, useRef, type ReactNode } from 'react';
import { Link, navigate, PaperLink, title, usePath } from '../router';
import { facts, fmt, usePdf, useSiteData, type SiteData } from '../siteData';
import { SiteHeader } from './Chrome';
import { ExampleCard } from './Example';

const Draft = () => <span className="draft">draft</span>;

function slides(d: SiteData | null): { title: string; body: ReactNode }[] {
  const f = d ? facts(d) : null;
  return [
    { title: 'Ember', body: <div className="s-title">
      <p className="big">Will a fire keep burning in the air we plan to breathe on the Moon and Mars?</p>
      <p className="muted">NASA Space Apps Challenge 2026</p>
      <p className="muted">Team: names and roles <Draft /></p></div> },
    { title: 'The problem', body: <ul className="s-list">
      <li>Habitats plan <b>more oxygen at lower pressure</b>: our Moon-base setting is 34 % O₂ at 8.2 psi, against 21 % at 14.7 psi on the ISS.</li>
      <li>In low gravity, hot gas does not rise, so flames behave differently from fires on Earth.</li>
      <li>Engineers need to know <b>where NASA has tested, and where nobody has</b>, before they size a fan, a detector or a material.</li></ul> },
    { title: 'Who it is for', body: <ul className="s-list">
      <li><b>Spacecraft and habitat engineers</b>: set cabin oxygen, pressure and a fuel; get the chance a small fire keeps burning, its range, a tested / estimated / untested grade, the nearest NASA tests and a report.</li>
      <li><b>Test planners</b>: see the untested gap and where the next microgravity test would teach the most.</li>
      <li>Why it matters for the mission <Draft /></li></ul> },
    { title: 'The data', body: f && d ? <div className="s-nums">
      <div><b>{fmt(f.tests)}</b><span>NASA tests loaded, as published</span></div>
      <div><b>{f.experiments}</b><span>NASA experiments ({f.tables} tables)</span></div>
      <div><b>{fmt(f.outcome)}</b><span>with a measured outcome: {d.meta.gas.card.n_tests} gas jets ({d.meta.gas.investigation}, {d.meta.gas.psi_id}) and {d.meta.droplet.card.n_tests} drops ({d.meta.droplet.investigation}, {d.meta.droplet.psi_id})</span></div>
      <p className="muted">Nothing invented: every value traces to its table row. Values read from free-text notes are marked derived.</p></div>
      : <p className="muted">Live numbers appear when the engine is reachable.</p> },
    { title: 'How a check works', body: <ol className="s-list">
      <li>Set the cabin air, the fuel and the gravity.</li>
      <li>The engine measures the distance to NASA tests of the <b>same fuel</b>.</li>
      <li><b>Tested</b>: real outcomes answer. <b>Estimated</b>: the model, between tests. <b>Untested</b>: no number.</li>
      <li>Every estimate shows its range and what moves it most.</li>
      <li>The nearest NASA tests and a printable report back it up.</li></ol> },
    { title: 'Live: Moon-base air, a small gas leak', body: <div className="s-example"><ExampleCard /></div> },
    { title: 'Is it any good?', body: f && d ? <div className="s-nums two">
      <div><b>{f.gasBest?.auc?.toFixed(2)}</b><span>AUC, gas jets, on {f.gas.n_campaigns} NASA campaigns the model never saw (0.50 = chance). Brier {f.gasBest?.brier?.toFixed(3)} vs {f.gas.comparison[0].brier?.toFixed(3)} for always guessing the average.</span></div>
      <div><b>{f.dropBest?.auc?.toFixed(2)}</b><span>AUC, drops, on {f.drop.n_campaigns} unseen campaigns. Brier {f.dropBest?.brier?.toFixed(3)} vs {f.drop.comparison[0].brier?.toFixed(3)}.</span></div>
      <p className="muted">Whole campaigns are hidden in training. A model is used only if it beats the baseline. One command reproduces every score.</p></div>
      : <p className="muted">Live numbers appear when the engine is reachable.</p> },
    { title: "What's next", body: <ul className="s-list">
      <li>Partial-gravity tests would turn "untested" into answers for the Moon and Mars. <Draft /></li>
      <li>Solid-material tests that record whether the fire kept burning.</li>
      <li>An inert-gas share input, so CO₂ and helium mixes match how NASA ran them.</li>
      <li>Fit the flame simulator once verified solid-material points exist.</li></ul> },
    { title: 'Thank you', body: <div className="s-title">
      <p className="big">Try it: <Link className="link" to="/engine">launch the simulation</Link> · <PaperLink className="link">read the paper</PaperLink></p>
      <p className="muted">Data: NASA Physical Sciences Informatics. Contact and links <Draft /></p></div> },
  ];
}

export function Presentation() {
  const path = usePath();
  const { data } = useSiteData();
  const deck = slides(data);
  const n = Math.min(deck.length, Math.max(1, parseInt(path.split('/')[2] || '1', 10) || 1));
  const pdf = usePdf('/presentation.pdf');
  const box = useRef<HTMLDivElement>(null);
  const go = (k: number) => navigate(`/presentation/${Math.min(deck.length, Math.max(1, k))}`, true);

  useEffect(() => { title(`Presentation ${n}/${deck.length}`); }, [n, deck.length]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLElement && /INPUT|SELECT|TEXTAREA/.test(e.target.tagName)) return;
      if (['ArrowRight', 'PageDown', ' '].includes(e.key)) { e.preventDefault(); go(n + 1); }
      else if (['ArrowLeft', 'PageUp'].includes(e.key)) { e.preventDefault(); go(n - 1); }
      else if (e.key === 'Home') go(1);
      else if (e.key === 'End') go(deck.length);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  return (
    <div className="site deck-page" id="presentation">
      <SiteHeader here="presentation" />
      <div className="deck" ref={box}>
        {deck.map((s, i) => (
          <section key={s.title} className={'slide' + (i + 1 === n ? ' on' : '')} aria-hidden={i + 1 !== n} aria-label={`Slide ${i + 1} of ${deck.length}: ${s.title}`}>
            <span className="s-no">{i + 1} / {deck.length}</span>
            <h2>{s.title}</h2>
            <div className="s-body">{s.body}</div>
          </section>
        ))}
      </div>
      <div className="deck-bar" role="toolbar" aria-label="Slides">
        <button className="btn small" onClick={() => go(n - 1)} disabled={n === 1} aria-label="Previous slide">← Prev</button>
        <span className="num" aria-live="polite" id="slideNo">{n} / {deck.length}</span>
        <button className="btn small" onClick={() => go(n + 1)} disabled={n === deck.length} aria-label="Next slide">Next →</button>
        <span className="grow" />
        <button className="btn small" onClick={() => box.current?.requestFullscreen?.()}>Fullscreen</button>
        <button className="btn small" onClick={() => window.print()}>Print</button>
        {pdf && <a className="btn small" href="/presentation.pdf" download>Download PDF</a>}
      </div>
    </div>
  );
}
