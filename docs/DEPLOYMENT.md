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

## 5. Docker 启动（推荐）

仓库已包含 `Dockerfile`（`python:3.12-slim` + supervisor）、`deploy/supervisord.conf`、
`.dockerignore` 与 `docker-compose.yml`。容器内**同时**运行后端（127.0.0.1:8000，不对外）
与前端（0.0.0.0:7860，对外）。

```bash
# 本地起容器
docker compose up --build
# 打开 http://localhost:7860/
```

不会 Docker 时，macOS / Linux 可直接用等价脚本（与容器内命令一致）：

```bash
bash scripts/start_local.sh          # 默认 UI 7860 / API 8000
```

镜像体积关键点：`.dockerignore` 已排除 `data/datasets`、`member2_forensics/deliverables`、
`vendor/trufor/dataset/data` 等大体积资产，构建上下文只有约 10MB。

> 容器内 `DATA_DIR=/tmp/trueglow-data`，因为运行时上传/产物需要可写目录，
> 且平台（如 HF Spaces）可能以非 root 用户运行。**容器重启后这些文件会丢失**，
> 这符合演示场景；如需持久化请挂载卷并改回该变量。
>
> ⚠️ `deploy/supervisord.conf` 中**不要**给 `[supervisord]` 加 `user=root`。
> 部分平台以非 root 用户运行容器，supervisord 会因
> `Can't drop privilege as nonroot user` 直接退出，导致整个服务起不来
> （已实测复现并修正）。

## 6. 部署到 Hugging Face Spaces

### 方式一：一条命令（推荐）

```bash
export HF_TOKEN=hf_xxxxxxxx            # https://huggingface.co/settings/tokens（需 write 权限）
export HF_SPACE_ID=你的用户名/trueglow
python deploy/hf_deploy.py --dry-run   # 先看会传哪些文件
python deploy/hf_deploy.py             # 创建 Space 并上传
```

脚本用 `git archive` 只导出已跟踪文件（约 8.5MB，大体积资产自动排除），
自动生成带 `sdk: docker` frontmatter 的 Space README，然后创建并上传。
**它不会替你写密钥**，避免密钥进入 git 历史。

### 方式二：手动

在 Space 页面选 **Docker** SDK，然后把本仓库推上去。
**关键**：Space 仓库根目录的 `README.md` 顶部必须带 SDK frontmatter，否则不会按 Docker 构建 ——
可直接复制 `deploy/huggingface-README.md` 的内容作为该 Space 的 README。

随后在 **Settings → Variables and secrets** 配置：

| 类型 | 变量 | 建议 |
|---|---|---|
| Secret | `BEAUTYPROOF_API_KEY` | 随机长字符串 |
| Secret | `BEAUTYPROOF_ACCESS_CODE` | 演示口令 |
| Variable | `BEAUTYPROOF_RATE_LIMIT_PER_MINUTE` | `120` |
| Variable | `BEAUTYPROOF_RUNTIME_RETENTION_HOURS` | `24` |

注意：

- 默认 Space 是 **Public**，代码与构建日志公开可见；**不要把密钥写进仓库**，只用 Secrets。
- 健康检查走 `/healthz`（公开，不需要 Key），可作平台探针。
- 只暴露 7860 一个端口；后端 8000 仅监听容器内回环，公网不可达。
- 免费 CPU Space 会休眠，首次访问需等待唤醒。

## 7. 上线自查清单

- [x] 大体积演示资产移出版本库（被跟踪文件 479 → 203，体积 663MB → 9.0MB）
- [x] 部署配置：`Dockerfile` + `supervisord.conf` + `docker-compose.yml` + `.dockerignore`
- [x] 跨平台启动脚本 `scripts/start_local.sh`
- [x] 公网安全：API Key、限流、访问口令、CORS 收敛、运行时文件清理
- [x] 容器启动配置已实测：按 `.dockerignore` 暂存 + 全新环境 + supervisord 起双进程，
      前端 7860 / 后端 8000 均正常，鉴权 401/200 符合预期（非 root 用户下验证）
- [x] 一键部署脚本 `deploy/hf_deploy.py`（需自备 `HF_TOKEN`，故未代跑）
- [ ] **在 Hugging Face 创建 Space 并上传**（需你的 HF 账号，见 §6）
- [ ] 历史瘦身（可选）：历史 Blob 仍在，仓库总体积不降；彻底瘦身须重写历史，需团队知情
- [ ] 真实模型（可选）：当前五个 Tool 为 Mock 实现，无需权重即可跑通全流程
