import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  root: resolve('./src'),
  base: '/static/',
  server: {
    host: '0.0.0.0',
    port: 5173,
    watch: {
      usePolling: true,
    },
    origin: 'http://localhost:5173',
  },
  build: {
    outDir: resolve('../dist'),
    assetsDir: '',
    manifest: true,
    emptyOutDir: true,
    rollupOptions: {
      input: {
        main: resolve('./src/main.js'),
      },
    },
  },
})