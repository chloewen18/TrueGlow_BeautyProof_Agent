# TrueGlow 映真 · BeautyProof Agent

面向美妆内容生态的 AI 内容核验与信任辅助系统（L'Oréal 黑客松赛道 2）。
一个 Main Agent + 五个专业 Tool + 结构化证据层：`plan → execute → fuse → grade → report`。

> 本仓库已整合 5 位成员的交付物，按成员用文件夹区分（见下表）。

## 一、成员内容索引（文件夹 → 归属 → 状态）

| 路径 | 负责成员 | 内容 | 真实 / 模拟 |
|---|---|---|---|
| 仓库根 `backend/` `app.py` `api/` `schemas/` `examples/` | **成员 1**（Main Agent 与架构） | 5 Tool 接口、Agent 编排、证据融合、风险分级、报告 schema、Streamlit 前端 | 框架真实可跑 |
| `backend/app/tools/source_trace.py` `backend/app/integrations/metadata_parser.py` | **成员 2**（来源溯源） | EXIF/XMP/C2PA 解析骨架 + TruFor 接入约定 | EXIF 真实；C2PA 三态已规整；TruFor 待接官方权重 |
| `member2_forensics/` | **成员 2** | 独立版 `metadata_parser.py` + TruFor 官方使用参考 + FFHQR 许可说明 | 参考文档 |
| `backend/app/tools/before_after.py` + 数据集 | **成员 3**（底妆修饰与妆效归因） | Before/After 一致性接口；100 对 FFHQ-FHQR 数据集 | 接口已修（未计算→Unknown）；算法待做实 |
| `member3_dataset/` | **成员 3** | 100 对「原图 vs 修饰图」配对数据集（含 SHA256、许可、loader、划分） | 数据真实（248MB） |
| `backend/app/integrations/member4/` | **成员 4**（文本/评论/功效） | OCR（PP-OCRv5）、宣称提取、全文管线、功效证据 | 真实实现，非 mock |
| `member4_text/` | **成员 4** | Mini 功效证据 JSON/XLSX、OCR 脚本 | 真实 |
| `app.py` `api/` `assets/` `styles/` `tests/` | **成员 5**（前端/数据集/评测） | Streamlit 单页、API 路由、评测页 | 前端真实；评测数字已治理 |
| `docs/progress/` | 全员 | 分工与行动清单、群同步消息、项目白话详解 | 进度文档 |

## 二、已实现 vs 待完成

**已实现（真实）**
- 成员 1：Agent 全链路 + 5 Tool JSON 接口 + 报告 schema，可运行骨架。
- 成员 4：OCR 真实跑通 + 宣称词典 + 5 产品功效 JSON（测试集 20/20、盲测 20/30，F1 0.906）。
- 成员 3：100 对配对数据集（SHA256 校验通过、许可登记完整）。
- 成员 5：前端 5 分区 + 评测页（已去除手写假数字）。

**本轮已修复的正确性缺陷**
- `before_after`：未计算时归因强度/维度一律 `Unknown`（原先默认 `Strong`，等于没算就归功产品）。
- `C2paInfo`：状态扩为 6 态（`valid/invalid/absent/not_verified/unsupported_format/error`）。
- 评测数字：`benchmark_summary.json` 中手写占位（F1=0.78 等）已清空，改为「目标值/待测」口径。

**仍为模拟 / 待做实（演示前必须补）**
- `image_forensics`（图像鉴伪）：mock → 需成员 2 接 TruFor 官方权重。
- `before_after` 算法：mock → 需成员 3 用经典 CV 做实。
- `text_integrity` AI 文本检测：仅作提示，不用于定罪。
- 志愿者真实采集数据：测试集仅 10 对，需成员 5 启动采集。

## 三、快速开始

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r ../requirements.txt
.venv/bin/uvicorn app.main:app --reload --port 8000
# 打开 http://127.0.0.1:8000/docs
```

跑比赛 Demo（3 案例闭环）：`../.venv/bin/python -m demo.run_demo`
前端：`streamlit run app.py`（需安装 `requirements-ocr.txt` 中的 OCR 依赖）

## 四、成员 2 接 TruFor 的关键护栏

TruFor 官方 `score` **越高越可疑**；本系统 `integrity_score` **越高越完整**。
接入时必须：`integrity_score = 1 - trufor_score`。**不转换会把整条判断逻辑判反。**
权重与运行命令见 `member2_forensics/TRUFOR_REFERENCE.md`。

## 五、已知问题与注意事项（审计结论）

| 问题 | 处置 |
|---|---|
| Groupmate `TruFor_交付物` 为模拟、且分数方向/误报率错误 | **未纳入仓库**；改用官方权重（见 `member2_forensics/`） |
| Groupmate `full_pipeline_v1.py` 缺 `claim_extractor_mock_v2_1`，跑不起来 | **未纳入仓库**；功能已由 `backend/app/integrations/member4/` 取代 |
| `member3_dataset` 中 `ground_truth_strength` 全为占位 `medium` | 已注明：**不可当真值**训练/验证强度分类器 |
| FFHQR 为非商业许可（CC BY-NC-SA 4.0） | 赛事已确认接受；答辩需声明来源与许可 |
| Mirror-of-Truth 为另一组的项目 | 本仓库未引入；如需借用另行授权 |

## 六、目录结构（节选）

```
beautyproof-agent/
├── backend/                 # 成员1 核心 + 成员2/3/4 集成
│   ├── app/{tools,agent,integrations/llm,schemas,storage,logging}
│   └── demo/                # 3 案例 Demo
├── api/  app.py  assets/  styles/  tests/   # 成员5 前端与路由
├── schemas/  examples/  docs/               # 接口契约 / 示例 / 文档
├── member2_forensics/       # 成员2 独立交付 + TruFor 参考
├── member3_dataset/         # 成员3 100 对数据集（248MB）
├── member4_text/            # 成员4 功效证据与 OCR 脚本
└── docs/progress/           # 分工与行动清单等进度文档
```

> 密钥/权重/运行时数据不入库：`.venv/`、`backend/data/`、`data/models/`、`.env` 已在 `.gitignore` 排除。
