/* Engine overview (/engine): what the engine knows and where it stops. Every number comes from the API. */
import { CoverageChart, OutcomeBars } from '../components/Charts';
import { Link } from '../router';
import { facts, fmt, useSiteData } from '../siteData';

export function Tag({ kind }: { kind: 'nasa' | 'pub' | 'est' | 'val' }) {
  const t = { nasa: 'NASA test', pub: 'published value', est: 'model estimate', val: 'model validation' }[kind];
  return <span className={'tag ' + kind}>{t}</span>;
}

export function Overview() {
  const { data, err } = useSiteData();
  return (
    <section id="view-overview" className="view page" aria-labelledby="ovTitle">
      <div className="wrap">
        <div className="pagehead">
          <h2 id="ovTitle">Overview</h2>
          <p className="muted">What the engine has learned from, how well it does on NASA campaigns it never saw, and where the tests stop.</p>
        </div>
        {err && <p className="err" role="alert">Could not reach the API ({err}). No numbers are shown rather than stale ones.</p>}
        {!data && !err && <p className="loading">Loading the NASA tables…</p>}
        {data && <Body d={data} />}
      </div>
    </section>
  );
}

function Body({ d }: { d: NonNullable<ReturnType<typeof useSiteData>['data']> }) {
  const f = facts(d);
  const { gas, droplet } = d.meta;
  return (
    <>
      <div className="tiles" id="ovTiles">
        <div className="tile"><span className="tl">NASA tests loaded</span><b>{fmt(f.tests)}</b><span>from {f.tables} NASA PSI tables, as published</span><Tag kind="nasa" /></div>
        <div className="tile"><span className="tl">Tests with a measured outcome</span><b>{fmt(f.outcome)}</b><span>{gas.card.n_tests} gas jets ({gas.investigation}) · {droplet.card.n_tests} drops ({droplet.investigation}): the models learn from these</span><Tag kind="nasa" /></div>
        <div className="tile"><span className="tl">Gas-jet model, unseen campaigns</span><b>AUC {f.gasBest?.auc?.toFixed(2) ?? '—'}</b><span>Brier {f.gasBest?.brier?.toFixed(3)} vs {gas.card.comparison[0].brier?.toFixed(3)} for always guessing the average</span><Tag kind="val" /></div>
        <div className="tile"><span className="tl">Droplet model, unseen campaigns</span><b>AUC {f.dropBest?.auc?.toFixed(2) ?? '—'}</b><span>Brier {f.dropBest?.brier?.toFixed(3)} vs {droplet.card.comparison[0].brier?.toFixed(3)} for always guessing the average</span><Tag kind="val" /></div>
      </div>

      <div className="card">
        <span className="sec">Where NASA tested, and where the planned cabin air sits</span>
        <p className="muted fc-small">Each dot is one NASA microgravity test with a measured outcome. Anything far from the dots is untested: the engine gives no number there.</p>
        <div className="grid2">
          <CoverageChart id="covGas" title={`Gas-leak flames · ${gas.investigation} (${gas.psi_id})`} points={gas.points} presets={d.presets} yes={gas.outcome_yes} no={gas.outcome_no} />
          <CoverageChart id="covDrop" title={`Liquid fuel drops · ${droplet.investigation} (${droplet.psi_id})`} points={droplet.points} presets={d.presets} yes={droplet.outcome_yes} no={droplet.outcome_no} />
        </div>
      </div>

      <div className="card">
        <span className="sec">How the tests ended</span>
        <OutcomeBars rows={[
          { label: `Gas jets · ${gas.investigation}`, yes: gas.card.n_yes, no: gas.card.n_tests - gas.card.n_yes, yesText: gas.outcome_yes, noText: gas.outcome_no },
          { label: `Drops · ${droplet.investigation}`, yes: droplet.card.n_yes, no: droplet.card.n_tests - droplet.card.n_yes, yesText: droplet.outcome_yes, noText: droplet.outcome_no },
        ]} />
        <p className="muted fc-small">The share that kept burning reflects the conditions the researchers chose to test, not a real-world probability. Because most drops went out, always guessing "went out" is already right {Math.round((1 - droplet.card.n_yes / droplet.card.n_tests) * 100)} % of the time; that is why the models are judged on Brier score and log loss, not accuracy.</p>
      </div>

      <div className="cta-row">
        <Link className="btn primary" to="/engine/check">Run a fire check</Link>
        <Link className="btn" to="/engine/models">How the models were checked</Link>
        <Link className="btn" to="/engine/data">Browse the NASA tables</Link>
      </div>
    </>
  );
}
