/* A small pathname router: real URLs, Back/Forward work, every page can be linked. No dependency needed for
   five routes. Links are real <a href> so open-in-new-tab and copy-link work as usual. */
import { useSyncExternalStore, type AnchorHTMLAttributes, type MouseEvent } from 'react';

const listeners = new Set<() => void>();
const notify = () => listeners.forEach(f => f());
if (typeof window !== 'undefined') window.addEventListener('popstate', notify);
const subscribe = (f: () => void) => { listeners.add(f); return () => { listeners.delete(f); }; };

export function navigate(to: string, replace = false) {
  if (to === location.pathname + location.search + location.hash) return;
  try { history[replace ? 'replaceState' : 'pushState'](null, '', to); } catch { location.assign(to); return; }
  notify();
}

export function usePath() {
  return useSyncExternalStore(subscribe, () => location.pathname);
}

type LinkProps = AnchorHTMLAttributes<HTMLAnchorElement> & { to: string };

export function Link({ to, onClick, ...rest }: LinkProps) {
  const click = (e: MouseEvent<HTMLAnchorElement>) => {
    onClick?.(e);
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    e.preventDefault();
    navigate(to);
  };
  return <a {...rest} href={to} onClick={click} />;
}

/* Set the tab title for a page. */
export function title(page?: string) {
  document.title = page ? `${page} · Ember` : 'Ember: will a fire keep burning?';
}

/* The team's research paper (web/public/research-paper.pdf), opened in its own tab. */
export const PAPER_PDF = '/research-paper.pdf';

export function PaperLink(props: AnchorHTMLAttributes<HTMLAnchorElement>) {
  return <a {...props} href={PAPER_PDF} target="_blank" rel="noopener" />;
}
