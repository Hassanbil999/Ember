/* Research (/research): the method and evidence as a readable page. Numbers are live from the engine; the page
   prints to a clean PDF. If the team adds web/public/research-paper.pdf, a download link appears. */
import { useEffect, useState } from 'react';
import { api, type FireCheckRes } from '../api';
import { Link, title } from '../router';
import { facts, fmt, usePdf, useSiteData, type SiteData } from '../siteData';
import { SiteFooter, SiteHeader } from './Chrome';
import { ExampleCard } from './Example';

const pct = (p: number) => `${Math.round(p * 100)} %`;

/* Every fuel in Moon-base air (34 % O₂, 8.2 psi), microgravity: what the engine says today. */
function useMoonAir(d: SiteData | null) {
  const [rows, setRows] = useState<{ fuel: string; kind: string; res: FireCheckRes | null }[] | null>(null);
  useEffect(() => {
    if (!d) return;
    const reqs = [
      ...d.meta.gas.fuels.map(fuel => ({ kind: 'Gas jet, 0.5 mg/s', req: { problem: 'gas' as const, fuel, fuel_flow: 0.5, d0_mm: 3 } })),
      ...d.meta.droplet.fuels.map(fuel => ({ kind: 'Drop, 3 mm, nitrogen', req: { problem: 'droplet' as const, fuel, fuel_flow: 1, d0_mm: 3 } })),
    ];
    Promise.all(reqs.map(r => api.fireCheck({ ...r.req, o2_pct: 34, psi: 8.2, gravity_g: 0, diluent: 'N2' }).catch(() => null)))
      .then(out => setRows(reqs.map((r, i) => ({ fuel: r.req.fuel, kind: r.kind, res: out[i] }))));
  }, [d]);
  return rows;
}

export function Research() {
  const { data, err } = useSiteData();
  const f = data ? facts(data) : null;
  const moon = useMoonAir(data);
  const pdf = usePdf('/research-paper.pdf');
  useEffect(() => { title('Research'); }, []);
  const outcomeTables = data ? data.tables.filter(t => t.dataset === data.meta.gas.dataset || t.dataset === data.meta.droplet.dataset) : [];
  return (
    <div className="site" id="research">
      <SiteHeader here="research" />
      <article className="paper">
        <header className="paper-head">
          <span className="kicker">Research</span>
          <h1>Will a small fire keep burning in Moon-base air? What NASA's microgravity tests can and cannot say</h1>
          <p className="meta">Ember · NASA Space Apps Challenge 2026 · numbers are live from the engine</p>
          <div className="cta">
            <button className="btn small" onClick={() => window.print()}>Print / save as PDF</button>
            {pdf && <a className="btn small" href="/research-paper.pdf" download>Download the paper (PDF)</a>}
            <Link className="btn ember small" to="/engine">Launch simulation</Link>
          </div>
          {err && <p className="err">The engine is not reachable ({err}).</p>}
        </header>

        <section><h2>1. Question</h2>
          <p>Habitats for the Moon and Mars plan cabin air with more oxygen at lower pressure than the ISS. The challenge brief names 30 % oxygen or more at 10.2 psi or less; our Moon-base setting uses 34 % at 8.2 psi, against 21 % at 14.7 psi on the ISS. More oxygen makes fires easier to start and keep; lower gravity removes the buoyant flow that feeds a flame on Earth. We ask a narrow question an engineer can act on: <b>for a given cabin air and fuel, did NASA see a small fire keep burning, and how sure can we be between and beyond its tests?</b></p>
        </section>

        <section><h2>2. Data</h2>
          <p>All test data comes from NASA's Physical Sciences Informatics (PSI) experimental tables, loaded as published: impossible values are flagged, never corrected, and values read from free-text notes are marked derived.{f ? ` ${fmt(f.tests)} tests from ${f.tables} tables are loaded; ${f.tablesWithTests} hold per-test rows.` : ''} Only two tables record whether a fire kept burning, and the estimates learn from those alone:</p>
          <ul>
            {data && <>
              <li><b>{data.meta.gas.investigation}</b> ({data.meta.gas.psi_id}): gas jets of ethane, propane and butane, some diluted in nitrogen; {data.meta.gas.card.n_tests} tests with an outcome ({data.meta.gas.card.n_yes} {data.meta.gas.outcome_yes}). "Stayed lit" means still burning when the researchers ended the run.</li>
              <li><b>{data.meta.droplet.investigation}</b> ({data.meta.droplet.psi_id}): single drops of n-heptane and methanol; {data.meta.droplet.card.n_tests} tests with an outcome ({data.meta.droplet.card.n_yes} {data.meta.droplet.outcome_yes}), plus the measured burning-rate constant and the drop size when a flame died.</li>
            </>}
          </ul>
          {data && (
            <div className="tablebox"><table id="psiTables">
              <thead><tr><th>NASA table</th><th>PSI id</th><th>DOI</th><th className="n">Tests</th></tr></thead>
              <tbody>{data.tables.map(t => (
                <tr key={t.id} className={outcomeTables.includes(t) ? 'chosen' : ''}>
                  <td>{t.title.replace(/ \(NASA PSI-.*$/, '')}{outcomeTables.includes(t) && <span className="badge">used by the models</span>}</td>
                  <td className="num">{t.psi_id}</td>
                  <td>{t.doi ? <a className="link" href={`https://doi.org/${t.doi}`} target="_blank" rel="noreferrer">{t.doi}</a> : '—'}</td>
                  <td className="n">{fmt(t.points_count)}</td>
                </tr>))}</tbody>
            </table></div>
          )}
        </section>

        <section><h2>3. Method</h2>
          <p><b>Inputs.</b> Gas jets: oxygen, pressure, fuel flow, the fuel's carbon number and its share of the jet. Drops: oxygen, pressure, starting drop size, fuel, and the share of CO₂ or helium in the air. Fuels are described by what they are made of, so "the same fuel" is well defined.</p>
          <p><b>Where an estimate is allowed.</b> A request is compared only with NASA tests of the same fuel. Each input is scaled by its spread in the tests, and the thresholds come from the tests themselves: closer than the median distance between a test and its nearest neighbour is <b>tested</b> (the real outcomes answer, the model cross-checks); inside every tested range and within twice the 95th percentile of the tests' own 5-neighbour distance is <b>estimated</b>; anything else, any gravity but microgravity, or a fuel with no tests is <b>untested</b> and gets no number.</p>
          <p><b>Models.</b> Logistic regression, random forest and a Gaussian process (one length scale per input) are compared with a baseline that always predicts the training average. Burning-rate constant and extinction drop size use the same families as regressors.</p>
        </section>

        <section><h2>4. Validation</h2>
          <p>Every score is out-of-campaign: training hides a whole NASA test campaign and then predicts it (grouped 5-fold cross-validation). Random splits would put near-repeats of a test on both sides and overstate skill. A classifier is used only if it beats the baseline on both Brier score and log loss; accuracy is not used, because when most tests end one way, always guessing that is already accurate.</p>
          {f && data && (
            <div className="tablebox"><table>
              <thead><tr><th>Question</th><th>Model used</th><th className="n">AUC</th><th className="n">Brier</th><th className="n">Baseline Brier</th><th className="n">Campaigns</th></tr></thead>
              <tbody>
                <tr><td>{data.meta.gas.question}</td><td>{f.gas.chosen ?? 'none'}</td><td className="n">{f.gasBest?.auc?.toFixed(3)}</td><td className="n">{f.gasBest?.brier?.toFixed(4)}</td><td className="n">{f.gas.comparison[0].brier?.toFixed(4)}</td><td className="n">{f.gas.n_campaigns}</td></tr>
                <tr><td>{data.meta.droplet.question}</td><td>{f.drop.chosen ?? 'none'}</td><td className="n">{f.dropBest?.auc?.toFixed(3)}</td><td className="n">{f.dropBest?.brier?.toFixed(4)}</td><td className="n">{f.drop.comparison[0].brier?.toFixed(4)}</td><td className="n">{f.drop.n_campaigns}</td></tr>
              </tbody>
            </table></div>
          )}
          <p><b>Uncertainty.</b> A chance estimate is shown with the lowest and highest answer of five models, each trained without one group of campaigns. Measured quantities carry a 90 % range from the errors on unseen campaigns. Both are honest about campaign-to-campaign variation but are not a full uncertainty analysis: the 90 % coverage is computed on the same errors that set the range, and the model choice and its reported score come from the same cross-validation, so scores may be slightly optimistic. Charts: <Link className="link" to="/engine/stats">Statistics</Link>.</p>
        </section>

        <section><h2>5. Results</h2>
          <p>The engine's answer for every tested fuel in Moon-base air (34 % O₂, 8.2 psi), in microgravity:</p>
          {moon ? (
            <div className="tablebox"><table id="moonAir">
              <thead><tr><th>Fuel</th><th>Case</th><th>Grade</th><th className="n">Chance it keeps burning</th><th>Why</th></tr></thead>
              <tbody>{moon.map(r => (
                <tr key={r.fuel}><td>{r.fuel}</td><td>{r.kind}</td>
                  <td>{r.res ? <span className={'pill mini zone-' + r.res.zone}>{r.res.zone}</span> : '—'}</td>
                  <td className="n">{r.res?.estimate ? `${pct(r.res.estimate.probability)} (${pct(r.res.estimate.low)}–${pct(r.res.estimate.high)})` : '—'}</td>
                  <td className="why">{r.res ? (r.res.reasons[0] ?? (r.res.zone === 'tested' ? 'NASA tests at nearly these conditions' : 'between NASA tests of this fuel')) : 'engine not reachable'}</td></tr>
              ))}</tbody>
            </table></div>
          ) : <p className="loading">Asking the engine…</p>}
          <p>Near Moon-base air, only some of the diluted gas jets were tested; the pure gases were tested near sea-level pressure only, and no drop was tested below about 10 psi. The gap is the result: it shows where the next microgravity test would teach the most.</p>
          <ExampleCard />
        </section>

        <section><h2>6. Reproduce</h2>
          <pre className="cmd"><code>python run.py start            # one command from a clean checkout → http://localhost:8000{'\n'}python run.py ingest predict   # retrain the models and rewrite the model cards</code></pre>
          <p>Every network step writes a committed snapshot, so a clean checkout runs offline and gives the same result; random seeds are fixed.</p>
        </section>

        <section><h2>7. References</h2>
          <ul className="refs">
            <li>NASA Physical Sciences Informatics experimental tables, each cited with its DOI in the data table above.</li>
            <li>NASA, <i>A Researcher's Guide to: Combustion Science</i> (2015), used for the quoted passages in Find data.</li>
            <li>Earth limiting oxygen values: Perry's Chemical Engineers' Handbook, 8th ed. (2007), §23, shown as a labelled reference, never as training data.</li>
            <li>OECD principles for the validation of (Q)SAR models, principle 3 (a defined domain of applicability).</li>
          </ul>
        </section>
      </article>
      <SiteFooter />
    </div>
  );
}
