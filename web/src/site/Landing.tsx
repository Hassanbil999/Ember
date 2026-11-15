/* Landing page (/): hero, three numbers, how it works, a live example, why it matters, one call to action.
   Every number comes from the engine. */
import { useEffect } from 'react';
import { Link, PaperLink, title } from '../router';
import { facts, fmt, useSiteData } from '../siteData';
import { SiteFooter, SiteHeader } from './Chrome';
import { ExampleCard } from './Example';
import { HeroField } from './HeroField';

const Icon = ({ d }: { d: string }) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={d} /></svg>;
const WHY = [
  { c: 'w1', icon: 'M6 3h12M8 3v6l-4 9a2 2 0 0 0 2 3h12a2 2 0 0 0 2-3l-4-9V3M7 15h10',
    h: 'Every test is expensive', p: 'A fire experiment in microgravity needs a drop tower, a parabolic flight or a slot on the ISS. Ember gets more out of the tests NASA already ran.' },
  { c: 'w2', icon: 'M12 3c1 3 5 5.5 5 10a5 5 0 0 1-10 0c0-2.5 1.5-4 2.5-5 .3 1.8 1.2 2.6 2 3 .3-3-1-5.5.5-8z',
    h: 'In space, there is nowhere to run', p: 'A crew cannot step outside a burning spacecraft or habitat. Fire has to be stopped by design, before launch.' },
  { c: 'w3', icon: 'M4 6h16M4 12h10M4 18h7M17 15l3 3-3 3',
    h: 'The data is scattered', p: "NASA's fire results sit in many tables, each in its own format. Ember cleans and connects them so research can build on them." },
];

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
          <span className="eyebrow">NASA Space Apps 2026</span>
          <h1>What If the Fire You Know <em>Doesn't Exist in Space?</em></h1>
          <div className="cta">
            <Link className="btn ember big" to="/engine" id="ctaEngine">Launch simulation</Link>
            <Link className="btn big" to="/presentation">Presentation</Link>
            <PaperLink className="btn big">View paper</PaperLink>
          </div>
        </div>
      </section>

      <section className="numbers" aria-label="Ember in numbers">
        {f ? <>
          <div className="n1"><b>{fmt(f.tests)}</b><span>NASA tests</span></div>
          <div className="n2"><b>{f.experiments}</b><span>NASA experiments</span></div>
          <div className="n3"><b>{fmt(f.outcome)}</b><span>fires with a known ending</span></div>
        </> : null}
      </section>

      <section className="sect" id="method" aria-labelledby="howTitle">
        <h2 id="howTitle">How it works</h2>
        <ol className="steps">
          <li><span>1</span><h3>Set the air and the fuel</h3><p>Oxygen, pressure, gravity and what is burning.</p></li>
          <li><span>2</span><h3>Ember finds the NASA tests</h3><p>The closest real tests of the same fuel.</p></li>
          <li><span>3</span><h3>Get a clear answer</h3><p>Tested, estimated or untested, with a range.</p></li>
        </ol>
      </section>

      <section className="sect" aria-label="Live example"><ExampleCard /></section>

      <section className="sect" aria-labelledby="whyTitle">
        <h2 id="whyTitle">Why it matters</h2>
        <div className="cards3">
          {WHY.map(w => <div key={w.h} className={'card why ' + w.c}><Icon d={w.icon} /><h3>{w.h}</h3><p>{w.p}</p></div>)}
        </div>
      </section>

      <section className="closing">
        <h2>Check your cabin air</h2>
        <Link className="btn ember big" to="/engine">Launch simulation</Link>
      </section>
      <SiteFooter />
    </div>
  );
}
