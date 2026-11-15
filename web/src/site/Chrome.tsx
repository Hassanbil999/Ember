/* Header and footer shared by the landing and presentation pages. One way into the engine: Launch simulation. */
import { Link, PaperLink } from '../router';

type Here = 'home' | 'presentation';

export function SiteHeader({ here }: { here: Here }) {
  const cur = (k: Here) => (here === k ? 'page' : undefined);
  return (
    <header className="site-top">
      <Link to="/" className="logo" aria-current={cur('home')}><span className="logo-mark" aria-hidden="true" />Ember</Link>
      <nav aria-label="Site" className="site-nav">
        <Link to="/presentation" aria-current={cur('presentation')}>Presentation</Link>
        <PaperLink>Paper</PaperLink>
      </nav>
      <Link className="btn ember small" to="/engine" id="hdrLaunch">Launch simulation</Link>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="site-foot">
      <span className="logo small"><span className="logo-mark" aria-hidden="true" />Ember</span>
      <span>NASA Space Apps Challenge 2026 · data from NASA Physical Sciences Informatics</span>
      <nav aria-label="Footer" className="site-nav">
        <Link to="/presentation">Presentation</Link><PaperLink>Paper</PaperLink><a href="/docs">API</a>
      </nav>
    </footer>
  );
}
