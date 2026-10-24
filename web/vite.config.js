import { defineConfig } from 'vite';
import { fileURLToPath } from 'node:url';

const dompurify = fileURLToPath(new URL('./node_modules/dompurify/dist/purify.es.mjs', import.meta.url));

export default defineConfig({
  base: './',
  build: { target: 'es2022' },
  plugins: [{
    name: 'c2g-m6-dompurify-runtime-remediation',
    enforce: 'pre',
    resolveId(source, importer) {
      if ((source === './dompurify/dompurify.js' && importer?.endsWith('/monaco-editor/esm/vs/base/browser/domSanitize.js')) || source.endsWith('/monaco-editor/esm/vs/base/browser/dompurify/dompurify.js')) return dompurify;
    },
  }],
});
