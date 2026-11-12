// Thin fetch layer. All requests go to /api (proxied to FastAPI by next.config rewrites).
const cache = new Map<string, Promise<any>>();

export async function get<T = any>(path: string, opts: { cache?: boolean } = {}): Promise<T> {
  const key = path;
  if (opts.cache !== false && cache.has(key)) return cache.get(key)!;
  const p = fetch(`/api${path}`).then(async (r) => {
    if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
    return r.json();
  });
  if (opts.cache !== false) {
    cache.set(key, p);
    p.catch(() => cache.delete(key));
  }
  return p;
}

export async function post<T = any>(path: string, body: unknown, as: "json" | "text" = "json"): Promise<T> {
  const r = await fetch(`/api${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return (as === "json" ? r.json() : r.text()) as Promise<T>;
}

export function clearCache(prefix = "") {
  for (const k of [...cache.keys()]) if (k.startsWith(prefix)) cache.delete(k);
}

export function download(name: string, content: string | Blob, type = "text/plain") {
  const blob = content instanceof Blob ? content : new Blob([content], { type });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
}
