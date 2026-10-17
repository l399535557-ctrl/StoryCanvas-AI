import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const target = env.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:8000'
  return {
    plugins: [react()],
    base: env.VITE_ASSET_BASE || '/',
    server: {
      proxy: Object.fromEntries(['/v1', '/health', '/images'].map(path => [path, {
        target, changeOrigin: true, timeout: 600_000, proxyTimeout: 600_000,
      }])),
    },
    build: { sourcemap: false },
  }
})
