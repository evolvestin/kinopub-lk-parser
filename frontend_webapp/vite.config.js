import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))

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
      protocol: 'wss',
      clientPort: 443,
      path: 'hmr'
    },
    fs: {
      allow: [
        '/app',
      ],
    },
  },
  build: {
    outDir: resolve(__dirname, 'dist'),
    manifest: true,
    emptyOutDir: true,
    rollupOptions: {
      input: 'src/main.js',
    },
  },
})