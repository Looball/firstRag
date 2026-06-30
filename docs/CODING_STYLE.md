# 编码规范

## 通用

- 保持现有仓库风格一致。
- 所有类、函数、方法必须有 docstring。
- 关键业务逻辑使用中文注释说明意图。
- 类型注解优先明确，避免无必要的 `Any` 扩散。
- 不把密钥、token、完整 API Key 写入日志、文档或提交。

## Python 后端

- 路由层使用 `APIRouter`，认证通过 `Depends(get_current_user_id)`。
- 权限校验在路由层完成，查询通过 repository。
- repository 中 SQL 使用 `%s` 占位符，禁止字符串拼接用户输入。
- 软删除数据查询必须过滤 `deleted_at IS NULL`。
- 服务层函数接收基本类型参数，不接收 HTTP 对象。
- 外部模型和 embedding 调用在服务层封装。

## TypeScript 前端

- 组件和工具函数保持职责单一。
- Next.js API Route 只负责代理、header 转发和错误适配。
- 动态路由 handler 显式声明 `params` 类型。
- API Key 不进入浏览器持久化存储。
- 流式接口保持 `Response` body 透传，避免破坏 SSE。

## 数据库

- `backend/app/db/sql/000_initial_schema.sql` 是当前空库初始化基线。
- 新表和结构变更从 `001_xxx.sql` 开始放入 `backend/app/db/sql/`，按编号递增。
- 不在增量 migration 中写入本地数据库导出的 `ALTER TABLE ... OWNER TO ...` 语句。
- 多表关联查询必须包含 `user_id` 隔离。
- 长流程任务使用状态字段和幂等保护，避免旧任务覆盖新结果。

## 测试与验证

- 后端测试目录：`backend/tests/`。
- 前端验证优先运行 `npm run lint` 和 `npm run build`。
- Python 轻量检查可使用：

```bash
cd backend
conda activate firstrag
python -m compileall app
```

依赖缺失时要如实说明，不伪造测试结果。
