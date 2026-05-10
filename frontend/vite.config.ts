import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    tailwindcss(),
  ],
  server: {
    port: 5173,
    proxy: {
      // Proxy all /api calls to FastAPI on port 6767
      '/api': {
        target: 'http://127.0.0.1:7101',
        changeOrigin: true,
      },

    },
  },
})
