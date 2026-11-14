/* Landing page (/). Structure borrowed from a past Space Apps winner (hero, features, method, worked example,
   why it matters, closing call to action); the content is ours and every number comes from the engine. */
import { useEffect } from 'react';
import { Link, title } from '../router';
import { facts, fmt, useSiteData } from '../siteData';
import { Limits } from '../views/FireCheck';
import { SiteFooter, SiteHeader } from './Chrome';
import { ExampleCard } from './Example';
import { HeroField } from './HeroField';

const ICON = {
  data: 'M4 5h16v14H4zM4 10h16M4 15h16M10 5v14',
  grade: 'M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7zM8.5 12l2.5 2.5 4.5-5',
  limits: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 7v6M12 16.5v.5',
  habitat: 'M3 20h18M5 20v-7a7 7 0 0 1 14 0v7M9 20v-4h6v4',
  plan: 'M4 4h16v16H4zM4 9h16M9 4v16M13 13h4M13 16h3',
  honest: 'M5 12l4 4 10-10',
};
const Icon = ({ d }: { d: string }) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={d} /></svg>;

export function Landing() {
  const { data } = useSiteData();
  const f = data ? facts(data) : null;
  useEffect(() => { title(); }, []);
  return (
    <div className="site" id="landing">
      <SiteHeader here="home" />
      <section className="hero">
        <HeroField />
        <div className="hero-in">
          <div className="badges"><span>NASA PSI data</span><span>Microgravity fire tests</span><span>Tested · Estimated · Untested</span></div>
          <h1>Will a fire <em>keep burning</em> in the air we plan to breathe?</h1>
          <p className="lede">Moon and Mars habitats plan richer oxygen at lower pressure. Set the cabin air and a fuel, and The Oxygen Edge answers from NASA's own microgravity fire tests: tested, estimated or untested, with its range and the tests behind it.</p>
          <div className="cta">
            <Link className="btn primary big" to="/engine" id="ctaEngine">Open the engine</Link>
            <Link className="btn big" to="/presentation">View presentation</Link>
            <Link className="btn big" to="/research">Read the research</Link>
            <a className="btn big ghost" href="#method">How it works</a>
          </div>
        </div>
      </section>

      <section className="band" aria-label="The engine in numbers">
        <div className="strip">
          {f ? <>
            <div><b>{fmt(f.tests)}</b><span>NASA tests loaded <span className="tag nasa">NASA test</span></span></div>
            <div><b>{f.tables}</b><span>NASA PSI tables, as published</span></div>
            <div><b>{fmt(f.outcome)}</b><span>tests with a measured outcome</span></div>
            <div><b>{f.gasBest?.auc?.toFixed(2)} · {f.dropBest?.auc?.toFixed(2)}</b><span>AUC on unseen NASA campaigns, gas jets · drops <span className="tag val">model validation</span></span></div>
          </> : <p className="muted">Live numbers appear here when the engine is reachable.</p>}
        </div>
      </section>

      <section className="sect" id="features" aria-labelledby="featTitle">
        <h2 id="featTitle">What it does</h2>
        <p className="muted sub">An engineering check for cabin fire risk, built only on what NASA measured.</p>
        <div className="cards3">
          <div className="card feat"><Icon d={ICON.data} /><h3>Real NASA tests</h3><p>{f ? `${fmt(f.tests)} tests from ${f.tables}` : 'Tests from the'} NASA PSI tables, loaded as published. Nothing is invented: every value traces to its table row.</p></div>
          <div className="card feat"><Icon d={ICON.grade} /><h3>A fire check with a grade</h3><p>Set oxygen, pressure, fuel, and drop size or leak size. Get the chance it keeps burning with its range, the burning rate for drops, what moves it most, and a tested / estimated / untested grade.</p></div>
          <div className="card feat"><Icon d={ICON.limits} /><h3>Limits on screen</h3><p>No number outside what NASA tested. The nearest real tests are always shown, and the report says what the result can and cannot support.</p></div>
        </div>
      </section>

      <section className="sect" id="method" aria-labelledby="methodTitle">
        <h2 id="methodTitle">How it works</h2>
        <p className="muted sub">The same steps for every check, and the same tests for every model.</p>
        <div className="cards2">
          <div className="card"><h3 className="acc-b">How a check works</h3><ol>
            <li>You set the cabin air, the fuel and the gravity.</li>
            <li>The engine measures how far that is from NASA tests of the same fuel.</li>
            <li>Close to a test: <b>tested</b>, and the real outcomes answer. Between tests: <b>estimated</b> by the model. Outside: <b>untested</b>, no number.</li>
            <li>An estimate comes with its range and what moves it most.</li>
            <li>The nearest NASA tests and a printable report back it up.</li>
          </ol></div>
          <div className="card"><h3 className="acc-c">How we check the models</h3><ol>
            <li>Training hides a whole NASA campaign, then predicts it.</li>
            <li>Every model is compared with always guessing the average.</li>
            <li>A model is used only if it beats that baseline on Brier score and log loss.</li>
            <li>Measured quantities carry a 90 % range taken from errors on unseen campaigns.</li>
            <li>One command retrains and reproduces every score.</li>
          </ol></div>
        </div>
      </section>

      <section className="sect" aria-label="Worked example"><ExampleCard /></section>

      <section className="sect" aria-labelledby="whyTitle">
        <h2 id="whyTitle">Why it matters</h2>
        <div className="cards3">
          <div className="card feat small"><Icon d={ICON.habitat} /><h3>Habitat design</h3><p>Richer oxygen at lower pressure changes how fires behave. Designers need to know what NASA has actually seen burn.</p></div>
          <div className="card feat small"><Icon d={ICON.plan} /><h3>Test planning</h3><p>The untested gap is visible, so it shows where the next microgravity test would teach the most.</p></div>
          <div className="card feat small"><Icon d={ICON.honest} /><h3>Answers that say "we don't know"</h3><p>A screening check that stops at the edge of the data instead of guessing past it.</p></div>
        </div>
      </section>

      <section className="sect" aria-label="Limits"><Limits /></section>

      <section className="sect closing">
        <h2>Check your cabin air</h2>
        <p className="muted">Start from ISS air or Moon-base air and see what NASA's tests say.</p>
        <div className="cta center">
          <Link className="btn primary big" to="/engine/check">Run a fire check</Link>
          <Link className="btn big" to="/engine">Open the engine</Link>
        </div>
      </section>
      <SiteFooter />
    </div>
  );
}
