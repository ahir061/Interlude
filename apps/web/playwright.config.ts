import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './browser-tests', timeout: 90_000, workers: 1,
  use: { baseURL: 'http://localhost:3000', headless: true, screenshot: 'only-on-failure' },
});
