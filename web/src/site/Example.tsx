/* The worked example: one real fire check, answered live by the engine at fixed inputs. */
import { Gauge } from '../components/Gauge';
import { Link } from '../router';
import { exampleLink, useExample } from '../siteData';

const ZONE: Record<string, string> = { tested: 'Tested', estimated: 'Estimated', untested: 'Untested' };

export function ExampleCard() {
  const res = useExample();
  const e = res?.estimate;
  return (
    <article className="example" id="example" aria-labelledby="exTitle">
      <div className="ex-text">
        <span className="live"><i />Live from the engine</span>
        <h3 id="exTitle">A small gas leak in Moon-base air</h3>
        <p>30 % ethane leaking at 0.5 mg/s into 34 % oxygen at 8.2 psi.</p>
        {res && <span className={'zone-pill ' + res.zone}>{ZONE[res.zone]}</span>}
        <Link className="btn ember" to={exampleLink}>Try it yourself</Link>
      </div>
      <Gauge p={e ? e.probability : null} low={e?.low} high={e?.high} label={e ? `chance it ${e.will}` : 'checking…'} />
      {res && (
        <ul className="ex-tests" aria-label="Closest NASA tests">
          {res.nearest.slice(0, 3).map(r => (
            <li key={r.code}><span className="num">{r.code}</span><span>{r.o2_pct} % · {r.psi} psi</span><span className={'out ' + (r.burned ? 'b' : 'o')}>{r.outcome}</span></li>
          ))}
        </ul>
      )}
    </article>
  );
}
