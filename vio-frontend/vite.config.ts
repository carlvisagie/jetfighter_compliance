import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  base: '/ui/vio-react/',
  build: {
    outDir: '../ui/vio-react',
    emptyOutDir: true,
  },
});
