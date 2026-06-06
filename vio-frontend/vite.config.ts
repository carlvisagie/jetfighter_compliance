import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  base: '/ui/vio2/',
  build: {
    outDir: '../ui/vio2',
    emptyOutDir: true,
  },
});
