import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api/management': {
        target: 'http://skill-management:8001',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/management/, ''),
      },
      '/api/evaluation': {
        target: 'http://skill-evaluation:8002',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/evaluation/, ''),
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
