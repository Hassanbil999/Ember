/* /admin/verify (SPEC §6): unverified test points next to their source quote and page; verify, edit, reject.
   Needs ADMIN_TOKEN (kept in this tab's sessionStorage only). Decisions are saved to data/curation/verifications.json. */
import { useEffect, useState } from 'react';
import type { TestPoint } from '../types';

type Item = TestPoint & { source_title: string | null; source_url: string | null };
const FIELDS: [keyof TestPoint, string][] = [['gravity_g', 'g'], ['o2_pct', 'O₂ %'], ['pressure_kpa', 'kPa'], ['flow_cm_s', 'Flow cm/s'], ['spread_mm_s', 'mm/s']];
const ORIGIN: Record<string, string> = { ai: 'AI-extracted', seed: 'Starter row', psi: 'NASA table (derived value)' };

export function AdminVerify() {
  const [token, setToken] = useState(() => { try { return sessionStorage.getItem('fa-admin') || ''; } catch { return ''; } });
  const [who, setWho] = useState(() => { try { return sessionStorage.getItem('fa-admin-who') || ''; } catch { return ''; } });
  const [data, setData] = useState<{ items: Item[]; counts: Record<string, number>; decisions: number } | null>(null);
  const [origin, setOrigin] = useState('');
  const [msg, setMsg] = useState('');
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState<Record<string, string>>({});

  async function call(path: string, init?: RequestInit) {
    const r = await fetch(path, { ...init, headers: { 'Content-Type': 'application/json', 'X-Admin-Token': token, ...(init?.headers || {}) } });
    const j = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(j.detail || `${r.status}`);
    return j;
  }
  async function load() {
    try { setData(await call('/api/admin/queue' + (origin ? `?origin=${origin}` : ''))); setMsg(''); }
    catch (e) { setData(null); setMsg(String((e as Error).message)); }
  }
  useEffect(() => { if (token) void load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [origin]);

  async function decide(code: string, action: 'verify' | 'reject' | 'edit', fields?: Record<string, unknown>) {
    if (action === 'reject' && !confirm(`Reject ${code}? It will be removed from the Atlas.`)) return;
    try {
      const r = await call(`/api/admin/test-points/${encodeURIComponent(code)}/${action}`, { method: 'POST', body: JSON.stringify({ by: who, fields }) });
      const fit = r.model_params ? Object.entries(r.model_params as Record<string, { n_points: number; source: string }>).map(([m, v]) => `${m}: ${v.source}`).join('; ') : '';
      setMsg(`${code}: ${action} saved. Model parameters: ${fit}`);
      setEditing(null); await load();
    } catch (e) { setMsg(`${code}: ${(e as Error).message}`); }
  }
  function saveToken(e: React.FormEvent) {
    e.preventDefault();
    try { sessionStorage.setItem('fa-admin', token); sessionStorage.setItem('fa-admin-who', who); } catch { /* private mode */ }
    void load();
  }

  return (
    <main style={{ overflow: 'auto' }}>
      <div className="dwrap">
        <h2 style={{ fontFamily: 'var(--font-display)', fontSize: 26 }}>Verify test points</h2>
        <p className="muted" style={{ margin: 0, maxWidth: '80ch' }}>Check each value against the quoted source text and page. Verified points can be used to fit the simulator (SPEC §8.4). NASA table rows can only be verified; AI-extracted and starter rows can also be edited or rejected. Decisions are written to <code>data/curation/verifications.json</code>: commit that file to keep them.</p>
        <form className="r1" onSubmit={saveToken}>
          <label className="sr" htmlFor="tok">Admin token</label>
          <input className="search" id="tok" type="password" placeholder="Admin token (ADMIN_TOKEN)" value={token} onChange={e => setToken(e.target.value)} autoComplete="off" />
          <label className="sr" htmlFor="who">Your name</label>
          <input className="search" id="who" type="text" placeholder="Your name or initials" value={who} onChange={e => setWho(e.target.value)} style={{ flex: '0 1 220px' }} />
          <button className="btn primary" type="submit">Load queue</button>
        </form>
        {msg && <p role="status" className={msg.includes('saved') ? 'muted' : 'err'}>{msg}</p>}
        {data && (
          <>
            <div className="chips" role="group" aria-label="Origin">
              {[['', 'All'], ['ai', 'AI-extracted'], ['seed', 'Starter rows'], ['psi', 'NASA tables']].map(([k, l]) => (
                <button key={k} className="chip" aria-pressed={origin === k} onClick={() => setOrigin(k)}>{l}{k && <span className="c">{data.counts[k] ?? 0}</span>}</button>
              ))}
            </div>
            <div className="tablebox"><table>
              <thead><tr><th>Test</th><th>Origin</th>{FIELDS.map(([, l]) => <th key={l} className="n">{l}</th>)}<th>Outcome</th><th>Source, page and quote</th><th>Why unverified</th><th><span className="sr">Actions</span></th></tr></thead>
              <tbody>{data.items.map(p => (
                <tr key={p.code}>
                  <td className="num">{p.code}<div className="muted">{p.sample_desc}</div></td>
                  <td>{ORIGIN[p.origin] ?? p.origin}</td>
                  {FIELDS.map(([f]) => <td key={String(f)} className="n">{editing === p.code && p.origin !== 'psi'
                    ? <input aria-label={`${p.code} ${String(f)}`} style={{ width: 70 }} value={draft[f as string] ?? ''} onChange={e => setDraft({ ...draft, [f as string]: e.target.value })} />
                    : (p[f] as number | null) ?? '—'}</td>)}
                  <td>{p.outcome_text}</td>
                  <td style={{ whiteSpace: 'normal', minWidth: 260 }}>
                    {p.source_url ? <a className="link" href={p.source_url} target="_blank" rel="noopener noreferrer">{p.source_title}</a> : (p.source_title ?? 'No source yet')}
                    {p.source_page && <> · {p.source_page}</>}
                    {p.source_quote && <div className="muted">“{p.source_quote}”</div>}
                  </td>
                  <td style={{ whiteSpace: 'normal', minWidth: 180 }} className="muted">{p.unverified_reason}</td>
                  <td><span style={{ display: 'flex', gap: 6 }}>
                    {editing === p.code
                      ? <><button className="btn small primary" onClick={() => decide(p.code, 'edit', Object.fromEntries(Object.entries(draft).filter(([, v]) => v !== '').map(([k, v]) => [k, +v])))}>Save</button>
                          <button className="btn small" onClick={() => setEditing(null)}>Cancel</button></>
                      : <><button className="btn small primary" onClick={() => decide(p.code, 'verify')}>Verify</button>
                          {p.origin !== 'psi' && <button className="btn small" onClick={() => { setEditing(p.code); setDraft(Object.fromEntries(FIELDS.map(([f]) => [f, p[f] == null ? '' : String(p[f])]))); }}>Edit</button>}
                          {p.origin !== 'psi' && <button className="btn small" onClick={() => decide(p.code, 'reject')}>Reject</button>}</>}
                  </span></td>
                </tr>
              ))}</tbody>
            </table></div>
            <p className="moremsg">{data.decisions} decisions recorded so far.</p>
          </>
        )}
        <p><a className="link" href="/#simulate">Back to the Atlas</a></p>
      </div>
    </main>
  );
}
