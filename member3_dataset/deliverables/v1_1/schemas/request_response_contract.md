# Main Agent 对接契约 v1.1.0

## Python 直接调用

```python
from beautyproof_tool import BeautyProofTool

tool = BeautyProofTool()
single = tool.analyze_single("image.jpg", request_id="task-001")
pair = tool.analyze_pair("before.jpg", "after.jpg", mask_path=None, request_id="task-002")
```

## HTTP 接口

- `GET /health`
- `POST /v1/analyze/single`：`multipart/form-data`，字段 `image`、可选 `request_id`
- `POST /v1/analyze/pair`：`multipart/form-data`，字段 `before`、`after`、可选 `mask`和 `request_id`

## Main Agent 只需依赖的稳定字段

- `schema_version`
- `tool`
- `request_id`
- `status`
- `mode`
- `engine`
- `provenance`
- `result`
- `evidence[]`
- `limitations[]`

Main Agent 应优先将 `evidence` 与其他 Tool 的结果融合，不应把任何单个 `score` 直接翻译成“造假”。

`result.comparison_reliability` 的值固定为 `Low / Medium / High / Unknown`。单图模式不存在 Before/After 比较，因此返回 `Unknown`。

`provenance.model_integrity` 是模型加载时对三份权重实际计算 SHA-256 后的结果。`content_provenance` 不由成员 3 模型检查，因此返回 `not_checked`，由成员 2 的 `image_forensics` Tool 补充。
