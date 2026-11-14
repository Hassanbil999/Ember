/* "Ask the Atlas" (SPEC §10): question → /api/ai/ask. Answers show numbered citations (resource + page).
   Without an API key the server answers 503 with the relevant NASA passages, which are shown instead. */
import { useState } from 'react';
import { api, type AskPassage, type AskResponse } from '../api';
import { Cited, type Ref } from './Cited';

export function AskBox({ onCite, titles }: { onCite: (ref: Ref) => void; titles: Record<string, string> }) {
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<AskResponse | null>(null);
  const [off, setOff] = useState<{ detail: string; passages: AskPassage[] } | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (q.trim().length < 3) return;
    setBusy(true); setErr(null); setRes(null); setOff(null);
    try {
      const r = await api.ask(q.trim());
      if ('detail' in r) setOff(r); else setRes(r);
    } catch (x) { setErr(String((x as Error).message || x)); }
    setBusy(false);
  }
  const refs: Ref[] = (res?.citations ?? []).map(c => ({ id: c.resource_id, page: c.page, title: c.title || titles[c.resource_id] || c.resource_id }));
  return (
    <section className="ask" aria-labelledby="askTitle">
      <span className="sec" id="askTitle">Ask the Atlas</span>
      <form onSubmit={submit} role="search">
        <label className="sr" htmlFor="askQ">Question</label>
        <input id="askQ" type="text" value={q} onChange={e => setQ(e.target.value)} maxLength={500} autoComplete="off"
          placeholder="e.g. Why does a flame look different in microgravity?" />
        <button className="btn primary" id="askBtn" type="submit" disabled={busy || q.trim().length < 3}>{busy ? 'Searching…' : 'Ask'}</button>
      </form>
      <div aria-live="polite">
        {err && <p className="err">Could not ask: {err}</p>}
        {res && (
          <>
            <p id="askAnswer"><span className="ai">{res.source === 'ai' ? 'AI' : 'DATA'}</span>
              {res.covered ? <Cited text={res.answer} refs={refs} onCite={onCite} /> : res.answer}</p>
            {res.note && <p className="src">{res.note}</p>}
            {res.covered && <p className="src">Every sentence cites the NASA passage it comes from. Answers can still be wrong: open the source to check.</p>}
          </>
        )}
        {off && (
          <>
            <p id="askAnswer" className="muted">{off.detail} Here are the NASA passages that match your question:</p>
            <ul className="src" style={{ margin: 0, paddingLeft: 18 }}>
              {off.passages.map((p, i) => (
                <li key={i}><button className="link" onClick={() => onCite({ id: p.resource_id, page: p.page, title: p.title })}>{p.title}</button>
                  {p.section ? ` · ${p.section}` : ''}: “{p.excerpt.slice(0, 160)}…”</li>
              ))}
            </ul>
          </>
        )}
      </div>
    </section>
  );
}
