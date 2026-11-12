import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    include: [
      'tests/components/**/*.spec.ts',
      'tests/stores/**/*.spec.ts',
      'tests/unit/**/*.spec.ts',
    ],
    setupFiles: ['./tests/setup.ts'],
    css: false,
    restoreMocks: true,
    clearMocks: true,
  },
})
