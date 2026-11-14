import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import { AdminVerify } from './views/AdminVerify';
import './styles.css';

const admin = location.pathname.startsWith('/admin');
createRoot(document.getElementById('root')!).render(<StrictMode>{admin ? <AdminVerify /> : <App />}</StrictMode>);
