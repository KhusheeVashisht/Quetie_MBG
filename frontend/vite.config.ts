import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: resolve(__dirname, '../quetie/web/static'),
    emptyOutDir: false,
  },
  server: {
    port: 5173,
    open: false,
  }
})
