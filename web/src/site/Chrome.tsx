/* Header and footer shared by the landing, research and presentation pages. */
import { Link } from '../router';
import { useSiteData } from '../siteData';

type Here = 'home' | 'research' | 'presentation';

export function SiteHeader({ here }: { here: Here }) {
  const cur = (k: Here) => (here === k ? 'page' : undefined);
  return (
    <header className="site-top">
      <Link to="/" className="logo" aria-current={cur('home')}><span className="logo-mark" aria-hidden="true" />The Oxygen Edge</Link>
      <nav aria-label="Site" className="site-nav">
        <Link to="/engine">Engine</Link>
        <Link to="/presentation" aria-current={cur('presentation')}>Presentation</Link>
        <Link to="/research" aria-current={cur('research')}>Research</Link>
      </nav>
      <Link className="btn primary small" to="/engine/check">Run a fire check</Link>
    </header>
  );
}

export function SiteFooter() {
  const { data } = useSiteData();
  const ids = data ? [...new Set(data.tables.map(t => t.psi_id).filter(Boolean))] : [];
  return (
    <footer className="site-foot">
      <div>
        <b>The Oxygen Edge</b> · NASA Space Apps Challenge 2026
        <p className="muted">Data: NASA Physical Sciences Informatics (PSI) experimental tables{ids.length ? ` (${ids.join(', ')})` : ''}, loaded as published. Every number on these pages comes from the running engine.</p>
      </div>
      <nav aria-label="Footer" className="site-nav">
        <Link to="/engine">Engine</Link><Link to="/presentation">Presentation</Link><Link to="/research">Research</Link><a href="/docs">API</a>
      </nav>
    </footer>
  );
}
