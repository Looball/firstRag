# 依赖安全审计策略

FirstRAG 使用 `scripts/npm_audit_policy.py` 校验前端 production dependencies，使用 `scripts/pip_audit_policy.py` 校验后端 Python production dependencies，并使用 Trivy 校验第一方 backend/frontend 镜像中的 OS packages。GitHub Actions 在 pull request、`main` push、手动触发和每周一计划任务中执行这些门禁。

## npm audit 策略

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

## pip-audit 策略

- CI 固定安装 `pip-audit==2.10.1`，对 `backend/requirements.txt` 执行 `--strict` 审计。
- 任何有 `fix_versions` 的 finding 都会阻断，必须升级依赖，禁止用例外绕过。
- 没有上游修复版本的 finding 默认也会阻断；只有完成可达性 triage 后，才能登记精确到 advisory ID、package 和 affected version 的限时例外。
- 例外最长有效 31 天；过期、package version 变化、finding 消失或 advisory ID 不再匹配都会阻断。
- resolver、网络、scanner 或 JSON 解析异常属于审计失败，不会被当作零 finding 放行。

当前 ChromaDB 例外记录在 `pip-audit-exceptions.json`。它只覆盖 `GHSA-F4J7-R4Q5-QW2C / chromadb / 1.5.9`：该漏洞需要攻击者直连 Chroma collection API 并提交恶意 model repository 与 `trust_remote_code=true`。FirstRAG 支持的 Compose 拓扑不映射 Chroma 端口，Nginx 也没有 Chroma upstream；如果部署时额外暴露 Chroma，该例外不再成立。

本地复核：

```bash
conda run -n firstrag python -m pip install pip-audit==2.10.1
conda run -n firstrag python scripts/pip_audit_policy.py
```

处理到期例外时：

1. 先检查 ChromaDB 是否已经发布修复版本，并同时升级 Python package 与 `chromadb/chroma` image。
2. 没有修复版本时重新核对 Compose、Nginx 和生产网络，确保 Chroma 仍未直接暴露。
3. 只有 triage 结论仍成立时，才能更新 `reviewed_on` 和最多 31 天后的 `expires_on`。

## Docker image OS package 策略

- CI 从当前 Dockerfile 构建 `firstrag-backend:ci` 和 `firstrag-frontend:ci`，不扫描本机历史镜像。
- Trivy 只负责 OS packages；Python 与 npm library findings 分别由上面的专用策略处理，避免同一 finding 重复管理。
- 有修复版本的 `HIGH` / `CRITICAL` OS finding 阻断；`ignore-unfixed=true` 避免上游尚无补丁时形成无法解除的永久红灯。
- Trivy Action 固定到 `v0.36.0` 的完整 commit SHA，并显式固定 Trivy `v0.72.0`，避免第三方 Action tag 漂移。
- 当前没有 `.trivyignore`；如未来确需例外，应先建立带到期日的结构化策略，不能直接添加永久忽略 ID。

本地可使用同版本 Trivy 复核：

```bash
docker build --file deploy/docker/backend.Dockerfile --tag firstrag-backend:ci .
docker build --file deploy/docker/frontend.Dockerfile --tag firstrag-frontend:ci .
trivy image --scanners vuln --pkg-types os --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 firstrag-backend:ci
trivy image --scanners vuln --pkg-types os --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 firstrag-frontend:ci
```
