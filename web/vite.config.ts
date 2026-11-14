import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Dev: Vite on :5173 proxies /api to the FastAPI server. Production: FastAPI serves web/dist itself.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': process.env.VITE_API_URL || 'http://127.0.0.1:8000' } },
  build: { outDir: 'dist', sourcemap: false, chunkSizeWarningLimit: 600 },
  test: { environment: 'node', include: ['src/**/*.test.ts'] },
} as any);
