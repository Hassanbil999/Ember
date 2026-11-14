/* Statistics (/engine/stats): the important numbers first; then from NASA tables to the model (cleaning, unsupervised
   groups in the test conditions, what the supervised Gaussian process learned); then how well each model predicts on
   NASA campaigns it never saw (one line per model); then where NASA tested. Everything comes from the API. */
import { useEffect, useState } from 'react';
import { api, type Pipeline } from '../api';
import { CoverageChart, RocChart } from '../components/Charts';
import { ChanceMap, ClusterChart, PipelineStrip } from '../components/PipelineCharts';
import { facts, fmt, useSiteData } from '../siteData';

export function Statistics() {
  const { data, err } = useSiteData();
  const [pipe, setPipe] = useState<Pipeline | null>(null);
  const [which, setWhich] = useState<'gas' | 'droplet'>('gas');
  useEffect(() => { api.pipeline().then(setPipe).catch(() => setPipe(null)); }, []);
  const f = data ? facts(data) : null;
  return (
    <section id="view-stats" className="view page" aria-labelledby="stTitle">
      <div className="wrap">
        <h2 id="stTitle" className="page-title">Statistics</h2>
        {err && <p className="err" role="alert">Could not reach the API ({err}).</p>}
        {!data && !err && <p className="loading">Loading…</p>}
        {data && f && (
          <>
            <div className="tiles" id="stTiles">
              <div className="tile t1"><b>{fmt(f.tests)}</b><span>NASA tests loaded</span></div>
              <div className="tile t2"><b>{fmt(f.outcome)}</b><span>fires with a known ending</span></div>
              <div className="tile t3"><b>{f.gasBest?.auc?.toFixed(2)}</b><span>gas-leak model score</span></div>
              <div className="tile t4"><b>{f.dropBest?.auc?.toFixed(2)}</b><span>fuel-drop model score</span></div>
            </div>

            {pipe && (
              <div className="card" id="pipe">
                <div className="card-head">
                  <h3 className="sub-h">From NASA tables to the model</h3>
                  <div className="chips" role="group" aria-label="Question">
                    {(['gas', 'droplet'] as const).map(k => <button key={k} className="chip" id={'pipe-' + k} aria-pressed={which === k} onClick={() => setWhich(k)}>
                      {k === 'gas' ? 'Gas leak' : 'Fuel drop'} · {pipe[k].investigation}</button>)}
                  </div>
                </div>
                <h4 className="step-h"><span>1</span>Cleaning</h4>
                <PipelineStrip v={pipe[which]} />
                <div className="grid2">
                  <div><h4 className="step-h"><span>2</span>Unsupervised: groups in the conditions</h4><ClusterChart v={pipe[which]} /></div>
                  <div><h4 className="step-h"><span>3</span>Supervised: the Gaussian process</h4><ChanceMap v={pipe[which]} /></div>
                </div>
              </div>
            )}

            <div className="card">
              <h3 className="sub-h">How well the models predict</h3>
              <p className="lead">Each line is a model tested on NASA campaigns it never saw. Higher is better; the diagonal is a coin flip. The score is the area under the line (1.00 = perfect).</p>
              <div className="grid2">
                <RocChart id="rocGas" title={`Gas leak · ${data.meta.gas.investigation}`} rows={f.gas.comparison} chosen={f.gas.chosen} />
                <RocChart id="rocDrop" title={`Fuel drop · ${data.meta.droplet.investigation}`} rows={f.drop.comparison} chosen={f.drop.chosen} />
              </div>
            </div>

            <div className="card">
              <h3 className="sub-h">Where NASA tested</h3>
              <p className="lead">Every dot is a microgravity test with a known ending. Far from the dots, Ember gives no number.</p>
              <div className="grid2">
                <CoverageChart id="covGas" title={`Gas leak · ${data.meta.gas.investigation}`} points={data.meta.gas.points} presets={data.presets} yes={data.meta.gas.outcome_yes} no={data.meta.gas.outcome_no} />
                <CoverageChart id="covDrop" title={`Fuel drop · ${data.meta.droplet.investigation}`} points={data.meta.droplet.points} presets={data.presets} yes={data.meta.droplet.outcome_yes} no={data.meta.droplet.outcome_no} />
              </div>
            </div>

            <p className="foot-note">{fmt(f.tests)} tests from {f.tables} NASA PSI tables · models: {data.meta.gas.investigation} ({data.meta.gas.psi_id}), {data.meta.droplet.investigation} ({data.meta.droplet.psi_id}) · validation: {f.gas.validation} · reproduce: <code>python run.py ingest predict</code></p>
          </>
        )}
      </div>
    </section>
  );
}
