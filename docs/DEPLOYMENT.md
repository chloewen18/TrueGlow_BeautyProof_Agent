# 部署说明

本文档面向**公网部署**。本地开发请直接看根目录 `README.md` 的「快速启动」。

## 1. 系统构成

| 角色 | 技术 | 默认端口 | 入口 |
|---|---|---|---|
| 前端工作台 | Streamlit | 8503 | `app.py` |
| 后端 Main Agent | FastAPI | 8000 | `backend/app/main.py` |

两个进程，前端通过 `BEAUTYPROOF_API_BASE_URL` 调用后端。部署时必须**同时运行两个进程**。

## 2. 环境变量

复制 `.env.example` 为 `.env` 后按需填写。

| 变量 | 作用 | 默认 |
|---|---|---|
| `BEAUTYPROOF_API_KEY` | 后端 API Key；设置后 `/api/*` 需携带请求头 `X-API-Key` | 空（关闭） |
| `BEAUTYPROOF_ACCESS_CODE` | 前端访问口令；设置后进入工作台需先输入 | 空（关闭） |
| `BEAUTYPROOF_CORS_ORIGINS` | 允许的跨域来源，逗号分隔 | 空（仅同源） |
| `BEAUTYPROOF_RATE_LIMIT_PER_MINUTE` | 单 IP 每分钟请求上限 | 120 |
| `BEAUTYPROOF_RUNTIME_RETENTION_HOURS` | 上传文件与检测产物保留时长 | 24 |
| `BEAUTYPROOF_API_BASE_URL` | 前端指向的后端地址 | `http://127.0.0.1:8000` |
| `BEAUTYPROOF_USE_MOCK` | `true` 时前端使用内置模拟数据，不请求后端 | `false` |

**公网部署建议至少设置前两项。** 两者留空时安全层整体关闭，仅适合本地开发。

## 3. 安全层行为

`backend/app/security.py` 按以下顺序拦截请求（外 → 内）：CORS → 限流 → API Key → 业务。

- 限流在鉴权外层，携带错误 Key 的暴力尝试同样会被限流。
- **公开例外**：`/healthz`、`/docs`、`/`、`/api/v1/uploads/*`、`/api/v1/artifacts/*`。
  其中 uploads/artifacts 必须公开，因为浏览器 `<img>`/`<video>` 无法携带自定义请求头；
  文件名本身是随机 UUID，不可枚举 —— 但**仍不应在公开演示中长期保留敏感图片**，请依赖保留期清理。
- 启动时会自动清理超过保留期的上传与产物文件。
- 限流为**进程内**实现；多实例部署需替换为 Redis 等共享存储。

## 4. 本地启动（macOS / Linux）

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # 轻量：Mock 模式，无 torch/paddle

export BEAUTYPROOF_API_KEY=your-key
export BEAUTYPROOF_ACCESS_CODE=your-code

# 终端 1：后端
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000

# 终端 2：前端
export BEAUTYPROOF_API_BASE_URL=http://127.0.0.1:8000
streamlit run app.py --server.port 8503
```

> Windows 可用仓库自带的 `scripts/start_local.ps1`。

## 5. 上线前置条件

- [ ] **仓库体积**：大体积演示资产（`member2_forensics/deliverables/`、`data/datasets/`、
      `vendor/trufor/dataset/data/*_COCO_*_list.txt`）已移出版本库，当前被跟踪文件约 9MB。
      注意：历史提交中的 Blob 仍在，GitHub 仓库总体积不会因此下降；如需彻底瘦身须重写历史。
- [ ] **部署配置**：仓库尚无 `Dockerfile` / `Procfile` / CI。双进程应用推荐 Docker + supervisord。
- [ ] **真实模型（可选）**：当前五个 Tool 为 Mock 实现，无需权重即可跑通全流程。
      接入真实模型需 `requirements-models.txt` 与 `data/models/` 下的权重。

## 6. 目标平台：Hugging Face Spaces

推荐用 **Docker SDK**（一个 Space 同时跑前端与后端）。创建 Space 时需要：

1. 在 Space 的 Settings → Variables and secrets 中配置上表的环境变量；
2. 容器内同时启动两个进程（docker-compose 或 supervisord），并让前端指向 `http://127.0.0.1:8000`；
3. 健康检查走 `/healthz`（公开，不需要 Key）。
