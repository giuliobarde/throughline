import path from "path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["tests/web/**/*.test.ts"],
    passWithNoTests: true,
  },
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
});
