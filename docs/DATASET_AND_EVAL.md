# 数据与评测

## 数据资源

- `data/datasets/FFHQ_FFHQR_100_pairs_v1/`：100 对原图与专业修饰图，包含数据卡、配对清单和划分文件。
- `member2_forensics/deliverables/v2/`：TruFor 输出、压缩困难样本及阈值分析。
- `member4_text/deliverables/`：宣称词典、功效证据库与文本测试题。
- 志愿者采集流程见[采集说明](VOLUNTEER_STARTER.md)；个人图片仅保存在本地，不计为已完成的独立验证。

## 运行评测

在项目根目录、配置模型与 OCR 后执行：

```powershell
.venv/Scripts/python.exe scripts/evaluate_integrated.py --member3-pairs 100 --trufor-live
```

结果入口为 `data/integrated_evaluation.json` 和 `data/member4_evaluation.json`，逐轮输出保存在不入库的 `data/evaluation_runs/`。评测工作台用于查看结果及运行状态。`data/benchmark_summary.json` 与模拟案例不能作为真实模型性能依据。

## 结果口径

| 模块 | 已有评测范围 | 局限 |
| --- | --- | --- |
| 修饰检测 | 100 对、200 张图片的探索性复测；TP 73、FN 27、FP 5、TN 95 | 尚未排除训练重叠，不代表跨人物或跨域泛化准确率 |
| 文案分析 | 20 题与 30 题的规范化宣称集合复测 | 题目曾用于迭代；不覆盖 OCR、极性、时长及证据来源的整体准确率 |
| TruFor | 33 份可解释标签的交付 NPZ 复算 | 属于已有输出复算；对应原图未全部提供，不能当作全部本机重跑 |
| 前后对比 | 条件估计与几何对齐后的差异展示 | 差异图不提供操作级真值，条件变化不证明产品因果 |

TruFor 的 `trufor_score` 越高越可疑，`integrity_score = 1 - trufor_score`。原始资料中名称与方向不一致时，应按这一口径解释。低可疑分不能排除细微修饰；工具无输出应视为未知。

后续独立验证需要按人物隔离数据，核查训练重叠，补充真实上妆、光照变化、压缩及不同帧负样本，并使用未参与规则迭代的新文本题。

## Verdict 级端到端评测（2026-09-26）

`scripts/evaluate_verdict.py` 对配对数据集逐张跑**完整 Main Agent**
（上传 → 工具调用 → 融合 → 分级 → 报告），统计最终 verdict 的表现，
与 `evaluate_integrated.py` 的单模块评测互补。

**口径**：同一宣称文案「原相机零滤镜，无磨皮无修图，妆效自然持久」下
- 原图：误指率 = verdict 为 `high_risk_misleading` 的占比，目标为 0
- 修饰图：信号捕获率 = verdict 为 `partially_suspicious` / `high_risk_misleading` 的占比

**首跑结果（前 30 对 = 60 张，0 报错，平均 7.9s/张）**

| 图片 | 数量 | 高风险误导 | 部分可疑 | 证据不足 |
|---|---|---|---|---|
| 原图 | 30 | **0** | 5 | 25 |
| 修饰图 | 30 | 0 | 24 | 6 |

- 原图误指率 **0%**：没有任何真实图被判定为高风险误导
- 修饰图信号捕获率 **80%**：6 张漏检（与成员3 stage1 图片级 27% 漏检相比略好，
  因融合层引入了 TruFor 与规则信号）
- 原图出现"部分可疑"（5/30）属预期行为：辅助信号误报（成员3 stage1 误报率约 5%），
  与"高风险误导"有本质区别，不构成错误指控

**局限**：样本仅前 30 对、单一数据集（通用专业修图）、单条宣称文案；
未覆盖美颜滤镜、视频、跨域场景。扩大样本与文案变体后数字会变化。
