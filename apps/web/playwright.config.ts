import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  use: { baseURL: "http://localhost:3100", channel: process.env.CI ? undefined : "chrome" },
  webServer: {
    command: "pnpm exec next dev -p 3100",
    url: "http://localhost:3100/feed",
    reuseExistingServer: !process.env.CI,
  },
});
