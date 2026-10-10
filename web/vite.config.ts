import react from '@vitejs/plugin-react';
import { configDefaults, defineConfig } from 'vitest/config';

// E2E points the proxy at its own replay-only API, so it never reuses a dev server.
const API_TARGET = process.env.JEV_API_TARGET ?? 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': { target: API_TARGET },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    // Playwright owns e2e/; Vitest would otherwise collect its *.spec.ts files.
    exclude: [...configDefaults.exclude, 'e2e/**'],
    css: true,
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/main.tsx', 'src/test/**', 'src/**/*.d.ts'],
      thresholds: { lines: 80, functions: 80, branches: 80, statements: 80 },
    },
  },
});
