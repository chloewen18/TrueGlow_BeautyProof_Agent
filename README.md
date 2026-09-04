# TrueGlow 映真 · Main Agent 骨架（成员 1 交付）

L'Oréal「AI鉴真专家」赛题 —— 面向美妆内容生态的 AI 内容核验与信任辅助系统。

本仓库是 **成员 1（Main Agent 与系统架构）** 的交付：

| 交付物 | 位置 | 状态 |
|---|---|---|
| 接口规范文档（P0 冻结物，目标 09-06） | `docs/API_SPEC.md` | ✅ v1.0 |
| 最终报告 JSON Schema（Markdown + 机器可读） | `docs/REPORT_SCHEMA.md` + `schemas/*.json` | ✅ |
| Main Agent 可运行骨架 | `backend/app/` | ✅ 已跑通 |
| Demo（比赛 3 案例闭环） | `backend/demo/` | ✅ |

## 架构

```
一个 Main Agent + 五个专业 Tool + 一个结构化证据层
plan（任务拆解）→ execute（调用 Tool）→ fuse（证据融合）→ grade（风险分级）→ report（报告生成）
```

- **5 个 Tool**：`page_understanding` / `source_trace` / `image_forensics` / `before_after` / `text_integrity`
  （当前为 Mock 实现，成员 2/3/4 交付真实模型后按同一契约替换，见 `app/tools/__init__.py`）
- **统一信封**：所有端点 `POST /api/v1/tools/{name}`，请求/响应 schema 见 `docs/API_SPEC.md` §4
- **风险分级**：4 级结论（已验证/部分可疑/证据不足/高风险误导）+ 3 个风险维度 + 决策路径可追溯
- **报告**：`full_report`（证据链）+ `trust_card`（Beauty Trust Card）
- **LLM 可插拔**：默认规则模板（离线可用），配置 DeepSeek 后自动升级解释质量
- **日志追踪**：每个 `request_id` 一条 JSONL（`data/logs/`），证据落盘（`data/evidence/`）

## 快速开始

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r ../requirements.txt   # 首次
.venv/bin/uvicorn app.main:app --reload --port 8000                     # 启动
```

打开 http://127.0.0.1:8000/docs 查看 OpenAPI 交互文档。

### 跑比赛 Demo（3 案例闭环）

```bash
cd backend
../.venv/bin/python -m demo.run_demo
```

- **案例 A**：真实但缺少来源信息 → `证据不足`（不因元数据缺失误判伪造）
- **案例 B**：After 图磨皮 + 曝光变化 + 宣称"原相机零滤镜" → `高风险误导`
- **案例 C**：创作者补交原视频 → 复核后结论更新为 `部分可疑` + 可信妆效凭证

### 一键核验
curl -X POST http://127.0.0.1:8000/api/v1/verify \
  -H 'Content-Type: application/json' -d @payload.json

# 单个 Tool（各成员自测）
curl -X POST http://127.0.0.1:8000/api/v1/tools/source_trace \
  -H 'Content-Type: application/json' \
  -d '{"tool":"source_trace","request_id":"t1","payload":{"files":[{"kind":"image","ref":"a.jpg"}]}}'

# 创作者补证复核
curl -X POST http://127.0.0.1:8000/api/v1/creators/review \
  -H 'Content-Type: application/json' -d @review.json

# 追踪日志 / 证据
curl http://127.0.0.1:8000/api/v1/logs/{request_id}
curl http://127.0.0.1:8000/api/v1/evidence/{request_id}
```

### 素材上传（成员 5 对接用，推荐路径）

```bash
# 1) 上传图片/视频 → 拿 media_ref / media_url
curl -F "files=@before.jpg" -F "files=@after.jpg" http://127.0.0.1:8000/api/v1/upload
# 2) 把 media_ref 填进 /verify 的 content.media[].ref（见 docs/API_SPEC.md §6.4）
# 3) 预览： curl http://127.0.0.1:8000/api/v1/uploads/<path>
```

> 也可在 Demo 阶段直接 `multipart/form-data` 调 `/verify`（表单字段 `payload` + `files`），后端自动注入 `media_ref`。依赖 `python-multipart`（已在 `requirements.txt`）。

### 前端 Mock 接入示例 JSON

仓库已生成三份**完整、无省略**的冻结响应，可直接接进 `mock_api.py`（切换真实 API 时 UI 无需重写）：

| 文件 | 场景 | 结论 |
|---|---|---|
| `examples/case_a_response.json` | 真实但缺来源 | `insufficient_evidence` |
| `examples/case_b_response.json` | 磨皮 + 曝光变化 + "原相机零滤镜" | `high_risk_misleading` |
| `examples/case_c_review_response.json` | 创作者补证复核 | `high_risk_misleading` → `partially_suspicious` + 凭证 |

由 `backend/demo/generate_examples.py` 经真实端点生成，结构与联调完全一致。

## 启用 DeepSeek 解释（可选）

```bash
cp ../.env.example ../.env   # 修改：
# LLM_PROVIDER=deepseek
# DEEPSEEK_API_KEY=sk-xxx
```

不配置则走规则模板，完全离线可用。

## 目录结构

```
beautyproof-agent/
├── docs/
│   ├── API_SPEC.md          # 接口规范（P0 冻结物）
│   └── REPORT_SCHEMA.md     # 最终报告 JSON schema 说明
├── schemas/                 # 机器可读 JSON Schema（report/evidence/trust_card）
├── examples/               # 三份完整冻结响应 JSON（前端 Mock 接入用）
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI 入口
│   │   ├── media.py         # 素材上传 / 回流（/api/v1/upload、/api/v1/uploads）
│   │   ├── config.py        # 环境配置
│   │   ├── schemas/         # Pydantic 模型（信封/Tool/证据/报告）
│   │   ├── tools/           # 5 个 Tool（Mock 实现 + HTTP 端点 + 注册表）
│   │   ├── agent/           # planner / orchestrator / fuser / grader / reporter
│   │   ├── llm/             # LLM Provider（mock + deepseek）
│   │   ├── logging/         # JSONL 追踪日志
│   │   └── storage/         # 证据层 JSON 落盘
│   └── demo/                # 比赛 3 案例闭环 Demo（含 generate_examples.py）
└── requirements.txt / .env.example
```

## 成员对接快速索引

| 成员 | 对接点 |
|---|---|
| 成员 2/3/4 | 替换 `app/tools/*.py` 中对应 mock handler（契约见 `docs/API_SPEC.md` §5），可先用 `curl POST /api/v1/tools/{name}` 自测 |
| 成员 5 | `POST /api/v1/verify` + `POST /api/v1/creators/review`；素材上传见 `docs/API_SPEC.md §6.4`（推荐先 `/upload` 拿 `media_ref`）；渲染 `report.trust_card`（必填字段见 §6.5）；高级视图 `trust_card.advanced`（固定英文键见 §6.5）；Mock 阶段直接用 `examples/*.json` 三份完整 JSON |
