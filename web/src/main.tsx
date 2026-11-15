import { lazy, StrictMode, Suspense } from 'react';
import { createRoot } from 'react-dom/client';
import { PAPER_PDF, usePath } from './router';
import { Landing } from './site/Landing';
import './styles.css';
import './site.css';
import './tokens.css';

// Old links (/#simulate, /#data, with the simulator settings and filters in the query) keep working.
if (location.pathname === '/' && /^#(simulate|data)\b/.test(location.hash)) {
  history.replaceState(null, '', (location.hash.startsWith('#data') ? '/engine/data' : '/engine') + location.search);
}

// The research page is now the team's paper as a PDF; old /research links open it.
if (location.pathname.startsWith('/research')) location.replace(PAPER_PDF);

// The landing page loads first and alone; the engine (simulator, shaders, data finder) loads when opened.
const Engine = lazy(() => import('./Engine').then(m => ({ default: m.Engine })));
const Presentation = lazy(() => import('./site/Presentation').then(m => ({ default: m.Presentation })));
const AdminVerify = lazy(() => import('./views/AdminVerify').then(m => ({ default: m.AdminVerify })));

function Root() {
  const path = usePath();
  const page = path.startsWith('/admin') ? <AdminVerify />
    : path.startsWith('/engine') ? <Engine />
    : path.startsWith('/research') ? null
    : path.startsWith('/presentation') ? <Presentation />
    : <Landing />;
  return <Suspense fallback={<p className="loading" style={{ padding: 24 }}>Loading…</p>}>{page}</Suspense>;
}

createRoot(document.getElementById('root')!).render(<StrictMode><Root /></StrictMode>);
