---
title: TrueGlow 映真 · 内容信任工作台
emoji: 🌿
colorFrom: pink
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# TrueGlow 映真 · 内容信任工作台

面向美妆内容生态的 AI 内容核验与妆效归因演示：一个 Main Agent + 五个专业 Tool + 结构化证据层。

- **本文件用途**：创建 Hugging Face Space 时，把上面的 YAML frontmatter（`sdk: docker` 与 `app_port: 7860`）
  放在该 Space 仓库根目录 `README.md` 的最顶部，Space 才会按 Docker 构建。
- 容器内由 supervisor 同时启动 FastAPI 后端（127.0.0.1:8000）与 Streamlit 前端（0.0.0.0:7860）。
- 需要在 Space 的 **Settings → Variables and secrets** 配置 `BEAUTYPROOF_API_KEY` 与
  `BEAUTYPROOF_ACCESS_CODE`，否则演示环境不设防。
- 健康检查：`/healthz`。

完整部署说明见仓库内 `docs/DEPLOYMENT.md`。

> 免责声明：本项目为黑客松原型。检测信号不能证明创作者造假意图，前后差异不能证明产品因果功效；
> 模型输出仅供辅助判断，不构成真实核验结论。
