import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const clawProxyTarget =
  process.env.VITE_CLAW_PROXY_TARGET ?? 'http://127.0.0.1:9042'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: clawProxyTarget,
        changeOrigin: true,
      },
      '/healthz': {
        target: clawProxyTarget,
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.ts',
  },
})
