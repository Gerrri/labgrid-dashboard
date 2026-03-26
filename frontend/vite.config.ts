import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: '0.0.0.0',
    hmr:
      process.env.VITE_HMR_HOST || process.env.VITE_HMR_CLIENT_PORT
        ? {
            protocol: process.env.VITE_HMR_PROTOCOL || 'ws',
            host: process.env.VITE_HMR_HOST || 'localhost',
            clientPort: Number(process.env.VITE_HMR_CLIENT_PORT || '3000'),
          }
        : undefined,
    proxy: {
      '/api': {
        target:
          process.env.VITE_API_PROXY_TARGET ||
          process.env.VITE_API_URL ||
          'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
    },
    watch: {
      usePolling: true,
    },
  },
});
