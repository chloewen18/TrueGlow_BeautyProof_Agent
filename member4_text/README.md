# 成员 4 · 文本、评论与功效证据 — 交付物

本文件夹存放成员 4 的**独立交付物**（功效证据与 OCR 脚本）。
成员 4 的**正式管线代码**已集成在仓库根目录：`backend/app/integrations/member4/`
（`claim_extractor.py`、`full_pipeline.py`、`ocr_paddle_v2_1.py`、`evaluate.py`、`service.py`），均为真实实现，非 mock。

## 本文件夹内容

| 文件 | 说明 | 状态 |
|---|---|---|
| `Mini功效证据JSON(1).json` | 3–5 个代表产品的 mini 功效证据库 | ✅ 可用 |
| `Mini功效证据表格(1).xlsx` | 同上，表格版 | ✅ 可用 |
| `ocr_paddle_v2_1.py` | PP-OCRv5 文字识别脚本 | ✅ 可用 |

## 使用提示

- 功效证据 JSON 的字段来源建议在文档中补一行出处说明（哪个产品的宣称取自哪份材料）。
- 正式 OCR / 宣称提取 / 全文管线请直接用 `backend/app/integrations/member4/` 下的代码。

## ⚠️ 为什么没有包含 Groupmate 里的 `full_pipeline_v1.py`

该文件是成员 4 的早期独立脚本，**运行时会 `import claim_extractor_mock_v2_1` 但该模块未随包上传**，
因此脚本独立跑不起来（属于「检测出的问题」，按约定不纳入仓库）。其功能已被 `backend/app/integrations/member4/full_pipeline.py` 取代。
