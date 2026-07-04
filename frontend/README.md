# FirstRAG 前端说明

前端位于 `frontend/`，使用 Next.js App Router。浏览器请求 Next.js 页面和 API Route，API Route 再代理到 FastAPI backend。

## 默认启动

在仓库根目录通过 Docker Compose 启动完整链路：

```bash
docker compose up -d --build
docker compose ps
docker compose logs --tail=100 migrate backend worker frontend postgres
```

默认访问 `http://localhost:3000`。常规验证应基于 Compose 中的 frontend service。

## 本地专项调试

只有在需要单独调试 Next.js 页面或 API proxy 时，才在 `frontend/` 目录启动本地 dev server：

```bash
cd frontend
npm install
npm run dev
```

本地 dev server 默认将 API 请求代理到 `http://127.0.0.1:8000`，因此需要同时准备可用的 FastAPI backend。常规构建和验收仍以 Docker Compose 为准。

## 参考文档

- `../README.md`：项目总览和最短演示路径。
- `../docs/FRONTEND.md`：前端结构、API 代理和页面职责。
- `../docs/DEPLOYMENT.md`：Docker Compose、本地工作流和部署说明。
