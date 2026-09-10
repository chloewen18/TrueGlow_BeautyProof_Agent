# 成员 2 · 来源溯源与通用图像取证

本文件夹存放成员 2 的**独立交付物**与接⼝参考。集成后的正式实现在仓库根目录：

- 集成版元数据/C2PA 解析：`backend/app/tools/source_trace.py` + `backend/app/integrations/metadata_parser.py`
- 通用篡改检测（TruFor）接入：见下方「TruFor 参考」

## 本文件夹内容

| 文件 | 说明 | 状态 |
|---|---|---|
| `metadata_parser.py` | 成员 2 独立版 EXIF/XMP 解析脚本（Groupmate 原提交） | ✅ 可用；仅 EXIF，C2PA 未实现 |
| `TRUFOR_REFERENCE.md` | TruFor 官方模型使用参考（权重下载、运行命令、已知问题） | 📌 见下 |
| `FFHQR_LICENSE_NOTE.md` | FFHQR 数据集许可说明（非商业） | 📌 见下 |

## TruFor 参考（重要）

> ⚠️ **不要使用 Groupmate 里的 `TruFor_交付物` 文件夹**——那是早期模拟交付物，实测存在严重问题：
> 1. 8 张输出图中有图两两 MD5 完全相同（定位图=置信度图）；
> 2. 4 张测试图分辨率互不相同，非同批数据；
> 3. README 自承「评分基于模拟逻辑生成」；
> 4. 误报率计算错误（实际应为 0%，报告写 50%）。
>
> 正确做法：使用 **grip-unina 官方 TruFor 仓库**的权重做 inference（赛事接受非商业许可，已与赛方确认）。详见 `TRUFOR_REFERENCE.md`。

## 分数方向护栏（集成时必须遵守）

- TruFor 官方 `score`：**越高越可疑**（1.0 = 被篡改）。
- 本系统 `integrity_score`：**越高越完整**。
- 接入时必须转换：`integrity_score = 1 - trufor_score`。**不转换会把整条判断逻辑判反。**
