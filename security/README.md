# 依赖安全审计策略

FirstRAG 使用 `scripts/npm_audit_policy.py` 校验前端 production dependencies。GitHub Actions 在 pull request、`main` push、手动触发和每周一计划任务中执行该门禁。

策略边界：

- `high` 和 `critical` 永远阻断，禁止登记例外。
- 新出现的 `moderate` 默认阻断；只有完成可达性 triage 后，才能登记精确到 advisory ID 和 package 的限时例外。
- `low` 和 `info` 会输出 warning，但不阻断。
- 例外最长有效 31 天；超过 `expires_on` 后 CI 自动失败。
- 上游修复使 finding 消失后，遗留例外也会让 CI 失败，要求同步删除例外。
- npm registry、网络或 JSON 解析异常属于审计失败，不会被当作“无漏洞”放行。

当前 PostCSS 例外记录在 `npm-audit-exceptions.json`。它只覆盖 `GHSA-QX2V-QP2M-JG93 / postcss / moderate`，不覆盖 Next.js 的其它 advisory，也不能覆盖 severity 上升后的同一 finding。

本地复核：

```bash
conda run -n firstrag python scripts/npm_audit_policy.py
```

处理到期例外时：

1. 先检查 Next.js 最新兼容补丁是否已升级内嵌 PostCSS。
2. 能安全升级时更新依赖和 lockfile，运行 test、lint、build 后删除例外。
3. 仍无法升级时重新完成代码可达性 triage；只有结论仍成立时才能更新 `reviewed_on` 和最多 31 天后的 `expires_on`。
4. 不运行 `npm audit fix --force`，除非已经审查并接受它展示的所有 breaking changes。
