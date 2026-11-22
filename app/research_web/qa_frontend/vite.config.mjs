import { defineConfig } from 'vite';

export default defineConfig({
  base: './',
  define: { 'process.env.NODE_ENV': JSON.stringify('production') },
  build: {
    target: 'es2022',
    license: { fileName: 'THIRD_PARTY_LICENSES.md' },
    outDir: '../ui/qa-dist',
    emptyOutDir: true,
    lib: { entry: 'entry.tsx', formats: ['es'], fileName: () => 'qa.js', cssFileName: 'qa' },
  },
});
