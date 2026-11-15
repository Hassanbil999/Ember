/* Export dialog (prototype #dlg): preview CSV / JSON / BibTeX from POST /api/export, then download the real file. */
import { useEffect, useRef, useState } from 'react';
import { api } from '../api';

type Fmt = 'csv' | 'json' | 'bibtex';

export function ExportDialog({ ids, onClose }: { ids: string[]; onClose: () => void }) {
  const dlg = useRef<HTMLDialogElement>(null);
  const out = useRef<HTMLTextAreaElement>(null);
  const [fmt, setFmt] = useState<Fmt>('csv');
  const [file, setFile] = useState<{ text: string; filename: string; type: string } | null>(null);
  const [msg, setMsg] = useState('');

  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const d = dlg.current!;
    if (!d.open) { if (d.showModal) d.showModal(); else d.setAttribute('open', ''); }
    const onCancel = (e: Event) => { e.preventDefault(); closeRef.current(); };
    d.addEventListener('cancel', onCancel);
    return () => d.removeEventListener('cancel', onCancel);
  }, []);

  const key = ids.join(',');
  useEffect(() => {
    let stale = false;
    setFile(null); setMsg('');
    api.exportFile(ids, fmt).then(f => { if (!stale) setFile(f); }).catch(e => { if (!stale) setMsg('Export failed: ' + e.message); });
    return () => { stale = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, fmt]);

  function download() {
    if (!file) return;
    const url = URL.createObjectURL(new Blob([file.text], { type: file.type }));
    const a = document.createElement('a'); a.href = url; a.download = file.filename;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
    setMsg(`Saved ${file.filename}.`);
  }
  async function copy() {
    try { await navigator.clipboard.writeText(file?.text ?? ''); setMsg('Copied.'); }
    catch { out.current?.focus(); out.current?.select(); setMsg('Copy was blocked. The text is selected: press Ctrl+C or ⌘C.'); }
  }
  const preview = file ? (file.text.length > 60000 ? file.text.slice(0, 60000) + '\n… (preview truncated; the download has every row)' : file.text) : 'Preparing…';

  return (
    <dialog id="dlg" ref={dlg} aria-labelledby="dlgTitle">
      <div className="dlg">
        <h2 id="dlgTitle" style={{ fontFamily: 'var(--font-display)', fontSize: 'var(--fs-verdict)', fontWeight: 500 }}>Export</h2>
        <div className="seg" role="group" aria-label="Format" style={{ gridTemplateColumns: 'repeat(3,1fr)' }}>
          <button id="fCsv" aria-pressed={fmt === 'csv'} onClick={() => setFmt('csv')}>Test points (CSV)</button>
          <button id="fJson" aria-pressed={fmt === 'json'} onClick={() => setFmt('json')}>JSON</button>
          <button id="fCite" aria-pressed={fmt === 'bibtex'} onClick={() => setFmt('bibtex')}>Citations (BibTeX)</button>
        </div>
        <label htmlFor="out" className="sr">Export preview</label>
        <textarea id="out" ref={out} readOnly value={preview} />
        <div style={{ display: 'flex', gap: 10, justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap' }}>
          <span className="muted" id="copyMsg" style={{ fontSize: 'var(--fs-caption)' }} aria-live="polite">{msg || (file ? file.filename : '')}</span>
          <span style={{ display: 'flex', gap: 8 }}>
            <button className="btn primary" id="downloadBtn" disabled={!file} onClick={download}>Download</button>
            <button className="btn" id="copyBtn" disabled={!file} onClick={copy}>Copy</button>
            <button className="btn" id="closeDlg" onClick={() => { dlg.current?.close?.(); onClose(); }}>Close</button>
          </span>
        </div>
      </div>
    </dialog>
  );
}
