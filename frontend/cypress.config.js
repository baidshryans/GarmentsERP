import { defineConfig } from 'cypress';
import react from '@vitejs/plugin-react';

export default defineConfig({
  e2e: {
    baseUrl: 'http://localhost:5173',
    setupNodeEvents(on, config) {
      // optional event hooks
    },
  },
  component: {
    devServer: {
      framework: 'react',
      bundler: 'vite',
      viteConfig: {
        plugins: [react()],
      },
    },
  },
});
