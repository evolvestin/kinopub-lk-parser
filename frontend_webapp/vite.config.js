import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))

const isTunnel = process.env.WEBAPP_PUBLIC_URL && process.env.WEBAPP_PUBLIC_URL.startsWith('https://')

const hmrProtocol = process.env.VITE_HMR_PROTOCOL || (isTunnel ? 'wss' : 'ws')
const hmrPort = process.env.VITE_HMR_PORT ? parseInt(process.env.VITE_HMR_PORT) : (isTunnel ? 443 : 5173)
const hmrPath = process.env.VITE_HMR_PATH || 'hmr'

export default defineConfig({
  plugins: [vue()],
  root: __dirname,
  base: '/__vite__/', 
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    cors: true,
    allowedHosts: true,
    watch: {
      usePolling: true,
    },
    hmr: {
      protocol: hmrProtocol,
      clientPort: hmrPort,
      path: hmrPath
    },
    fs: {
      allow: [
        '/app',
      ],
    },
  },
  build: {
    outDir: resolve(__dirname, 'dist'),
    manifest: 'manifest.json',
    emptyOutDir: true,
    rollupOptions: {
      input: 'src/main.js',
    },
  },
})