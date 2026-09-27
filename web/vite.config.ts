import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// base './' -> funziona sia su GitHub Pages (/YOLO-Beer-Detector/) sia su un dominio proprio
export default defineConfig({
  plugins: [vue()],
  base: './',
  build: {
    chunkSizeWarningLimit: 900,
  },
})
