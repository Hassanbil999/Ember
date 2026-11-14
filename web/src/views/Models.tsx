/* Models (/engine/models): a read-only record of how each fire-check model was chosen and validated, from the
   model cards that `python run.py ingest predict` writes. No "train now" button: training is one reproducible command. */
import type { ModelRow, ProblemMeta } from '../api';
import { useSiteData } from '../siteData';
import { Tag } from './Overview';

const f3 = (v?: number | null, d = 3) => (v == null ? '—' : v.toFixed(d));

export function Models() {
  const { data, err } = useSiteData();
  return (
    <section id="view-models" className="view page" aria-labelledby="mdTitle">
      <div className="wrap">
        <div className="pagehead">
          <h2 id="mdTitle">Models</h2>
          <p className="muted">How each estimate is made and checked. Validation hides a whole NASA campaign while the model trains, then predicts it, so the scores answer "does this work on an experiment it has never seen?". A model is used only if it beats always guessing the average.</p>
        </div>
        {err && <p className="err" role="alert">Could not reach the API ({err}).</p>}
        {!data && !err && <p className="loading">Loading the model cards…</p>}
        {data && (['gas', 'droplet'] as const).map(k => <Card key={k} id={'model-' + k} m={data.meta[k]} />)}
        <div className="card">
          <span className="sec">Reproduce every number on this page</span>
          <pre className="cmd"><code>python run.py ingest predict</code></pre>
          <p className="muted fc-small">Retrains both models from the NASA tables in about two minutes and rewrites the model cards (<code>data/artifacts/predict/*.card.json</code>). Random seeds are fixed, so the same data gives the same scores.</p>
        </div>
      </div>
    </section>
  );
}

function Card({ id, m }: { id: string; m: ProblemMeta }) {
  const c = m.card;
  return (
    <article className="card" id={id}>
      <div className="mhead">
        <h3>{m.label} <span className="muted">· {c.question}</span></h3>
        <span className="muted fc-small">{m.investigation} ({m.psi_id}) <Tag kind="nasa" /></span>
      </div>
      <div className="facts">
        <div><b>{c.n_tests}</b><span>tests with an outcome</span></div>
        <div><b>{c.n_yes}</b><span>{c.outcome_yes}</span></div>
        <div><b>{c.n_tests - c.n_yes}</b><span>{c.outcome_no}</span></div>
        <div><b>{c.n_campaigns}</b><span>NASA campaigns</span></div>
      </div>
      <p className="fc-small"><b>Inputs:</b> {m.features.map(f => f.label + (f.unit ? ` (${f.unit})` : '')).join(' · ')}</p>
      <p className="fc-small"><b>Validation:</b> {c.validation}. <Tag kind="val" /></p>
      <Compare rows={c.comparison} chosen={c.chosen} kind="clf" />
      {Object.entries(c.regressions).map(([k, r]) => (
        <div key={k} className="reg">
          <p className="fc-small"><b>{r.label} ({r.unit})</b>: {r.meaning}. {r.n_tests} tests.</p>
          <Compare rows={r.comparison} chosen={r.chosen} kind="reg" />
          {r.interval90_half_width != null && (
            <p className="muted fc-small">90 % range: ± {r.interval90_half_width} {r.unit}, the 90th percentile of the errors on unseen campaigns. Those same errors set the range, so the {Math.round((r.interval90_coverage_on_unseen ?? 0) * 1000) / 10} % they cover is about 90 % by construction, not a separate check.</p>
          )}
        </div>
      ))}
      <p className="muted fc-small"><b>Range of a chance estimate:</b> the lowest and highest of five models, each trained with one group of campaigns left out (widened to include the final model's own estimate). It shows how much the answer depends on which campaigns were seen; it is not the full uncertainty.</p>
    </article>
  );
}

function Compare({ rows, chosen, kind }: { rows: ModelRow[]; chosen: string | null; kind: 'clf' | 'reg' }) {
  return (
    <div className="tablebox"><table>
      <thead><tr><th>Model</th>{kind === 'clf' ? <><th className="n">AUC</th><th className="n">Brier</th><th className="n">Log loss</th><th className="n">Accuracy</th></> : <th className="n">Mean abs. error</th>}<th>Beats baseline</th></tr></thead>
      <tbody>{rows.map(r => (
        <tr key={r.model} className={r.model === chosen ? 'chosen' : ''}>
          <td>{r.model}{r.model === chosen && <span className="badge">used</span>}</td>
          {kind === 'clf' ? <><td className="n">{f3(r.auc, 3)}</td><td className="n">{f3(r.brier, 4)}</td><td className="n">{f3(r.log_loss, 4)}</td><td className="n">{f3(r.accuracy, 3)}</td></> : <td className="n">{f3(r.mae, 4)}</td>}
          <td>{r.beats_baseline == null ? 'baseline' : r.beats_baseline ? 'yes' : 'no'}</td>
        </tr>))}</tbody>
    </table></div>
  );
}
