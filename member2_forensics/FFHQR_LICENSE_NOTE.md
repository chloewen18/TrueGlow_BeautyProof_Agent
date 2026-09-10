# FFHQR 数据集许可说明（成员 2/3 共用）

FFHQ-FHQR 是 FFHQ 的修饰版本，用于训练/评测「原图 vs 修饰图」识别。

- **FFHQR 整体许可**：CC BY-NC-SA 4.0（**非商业 + 相同方式共享**）。赛事接受非商业许可，已确认。
- **FFHQ 原图逐张许可不同**（在 `official_source_metadata.json` 中有登记）：含 CC-BY-NC、CC-BY、CC0、Public Domain、U.S. Govt. Works 等。
- 演示/评测前请确认所展示图片不违反其单项许可（尤其是 CC-BY 需署名、CC-BY-NC 不可商用）。

## 域差距提醒

FFHQ/FFHQ-FHQR 是 **1024×1024 无损 PNG 的生成人脸**，与真实手机拍摄 + 平台压缩的种草图存在域差距。在其上测得的检出率/误报率会**偏乐观**，正式指标需以自采真实数据为准（见成员 5 采集计划）。
