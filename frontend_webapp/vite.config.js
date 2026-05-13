import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __dirname = dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [vue()],
  root: __dirname,
  base: '/static/', // База должна совпадать с префиксом Django
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    watch: {
      usePolling: true,
    },
    hmr: {
      // Это критично: через туннель HMR работает только по WSS
      protocol: 'wss',
      // Мы не знаем адрес туннеля заранее, поэтому клиент должен 
      // использовать тот же хост, на котором открыта страница
      clientPort: 443,
    },
    fs: {
      allow: [
        resolve(__dirname, '..'),
      ],
    },
  },
  build: {
    outDir: resolve(__dirname, 'dist'),
    manifest: true,
    emptyOutDir: true,
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'src/main.js'),
      },
    },
  },
})