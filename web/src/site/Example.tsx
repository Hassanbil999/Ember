/* The worked example: one real fire check, answered by the running engine at fixed inputs. */
import { Link } from '../router';
import { exampleLink, useExample } from '../siteData';

const pct = (p: number) => `${Math.round(p * 100)} %`;
const ZONE: Record<string, string> = { tested: 'Tested', estimated: 'Estimated', untested: 'Untested' };

export function ExampleCard({ compact = false }: { compact?: boolean }) {
  const res = useExample();
  return (
    <article className="card example" id="example" aria-labelledby="exTitle">
      <div className="ex-head">
        <span className="badge live">live result from the engine</span>
        <h3 id="exTitle">Moon-base air, a small gas leak on fire</h3>
        <p className="muted">A 30 % ethane jet leaking 0.5 mg/s into 34 % oxygen at 8.2 psi, in microgravity: the gravity NASA tested. At Moon gravity the engine gives no number, because no NASA test burned anything there.</p>
      </div>
      {!res && <p className="loading">Asking the engine…</p>}
      {res && (
        <div className="ex-body">
          <div className="ex-left">
            <span className={'pill zone-' + res.zone}>{ZONE[res.zone]}</span>
            <p>{res.verdict}</p>
            {res.estimate && (
              <div className="stats"><div><b>{pct(res.estimate.probability)}</b><span>chance it {res.estimate.will}</span><span>range {pct(res.estimate.low)}–{pct(res.estimate.high)} <span className="tag est">model estimate</span></span></div></div>
            )}
          </div>
          <div className="ex-right">
            <span className="sec">The NASA tests behind it <span className="tag nasa">NASA test</span></span>
            <div className="tablebox"><table>
              <thead><tr><th>Test</th><th className="n">O₂ %</th><th className="n">psi</th><th className="n">Flow mg/s</th><th>Measured</th></tr></thead>
              <tbody>{res.nearest.slice(0, compact ? 3 : 4).map(r => (
                <tr key={r.code}><td className="num">{r.code}{r.close && <span className="badge">close</span>}</td><td className="n">{r.o2_pct}</td><td className="n">{r.psi}</td><td className="n">{r.fuel_flow}</td><td className={r.burned ? 'oc-b' : 'oc-o'}>{r.outcome}</td></tr>
              ))}</tbody>
            </table></div>
            <p className="muted fc-small">{res.model.investigation} ({res.model.psi_id}). <Link className="link" to={exampleLink}>Open this check in the engine</Link></p>
          </div>
        </div>
      )}
    </article>
  );
}
