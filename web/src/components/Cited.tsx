/* Text with [resource_id] or [resource_id p.N] markers → numbered citation buttons. The server has already
   dropped any citation that was not in the AI's context; markers that do not match a ref stay plain text. */
import { Fragment } from 'react';

export interface Ref { id: string; page?: number | null; title: string }

const MARK = /(\[[A-Za-z0-9_.-]+(?: p\.\d+)?\])/g;

export function Cited({ text, refs, onCite }: { text: string; refs: Ref[]; onCite: (r: Ref) => void }) {
  const key = (id: string, page?: number | null) => id + (page ? ` p.${page}` : '');
  const index = new Map(refs.map((r, i) => [key(r.id, r.page), i]));
  return <>{text.split(MARK).map((part, i) => {
    const m = /^\[([A-Za-z0-9_.-]+)(?: p\.(\d+))?\]$/.exec(part);
    const n = m ? index.get(key(m[1], m[2] ? +m[2] : null)) : undefined;
    if (n === undefined) return <Fragment key={i}>{part}</Fragment>;
    const r = refs[n];
    const label = r.title + (r.page ? `, page ${r.page}` : '');
    return <button key={i} className="cite" title={label} aria-label={`Source ${n + 1}: ${label}`} onClick={() => onCite(r)}>{n + 1}</button>;
  })}</>;
}
