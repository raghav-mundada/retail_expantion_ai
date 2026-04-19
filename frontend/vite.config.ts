import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    // Warn rather than error on chunks > 1 MB (leaflet + framer can be chunky)
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/react') || id.includes('node_modules/react-dom'))
            return 'react';
          if (id.includes('node_modules/leaflet') || id.includes('node_modules/react-leaflet'))
            return 'leaflet';
          if (id.includes('node_modules/framer-motion'))
            return 'framer';
          if (id.includes('node_modules/lucide-react'))
            return 'lucide';
        },
      },
    },
  },
})
