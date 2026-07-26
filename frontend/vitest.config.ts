import { configDefaults, defineConfig } from "vitest/config";

/** 单元测试不收集由 Playwright 独立运行的浏览器 E2E。 */
export default defineConfig({
  test: {
    exclude: [...configDefaults.exclude, "e2e/**"],
  },
});
