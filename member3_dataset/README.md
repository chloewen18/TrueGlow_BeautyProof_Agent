# 成员 3 · 底妆修饰与妆效归因 — 数据集交付

本文件夹是成员 3 的核心交付物：100 对「原图 vs 专业修饰图」配对数据集（FFHQ-FHQR），
含逐图 SHA256、许可登记、PyTorch dataloader 与 80/10/10 划分。

## 内容

```
member3_dataset/FFHQ_FFHQR_100_pairs_v1/
├── originals/        100 张原图（FFHQ 生成人脸，1024×1024）
├── retouched/        100 张对应修饰图
├── paired_manifest.csv   逐图元数据（含 SHA256、许可、标注）
├── paired_dataset.py     PyTorch DataLoader
├── DATASET_CARD.md       推荐使用方式 / 禁止假设
├── dataset_summary.json
├── official_source_metadata.json
├── sample_manifest.csv
├── errors.csv
└── splits/          train.txt / validation.txt / test.txt（80/10/10）
```

## ✅ 质量结论

- 100 对全部 `verified_pair`，SHA256 齐全，FFHQ 原图逐张带官方 MD5。
- 标注字段完整，并做了**逐图许可登记**（黑客松中超出平均水准）。
- 自带 PyTorch dataloader 与划分，可直接用于评测。

## ⚠️ 一个必须避开的陷阱：`ground_truth_strength`

`paired_manifest.csv` 中：

```
retouch_type                 = generic_professional_retouch   (100/100)
retouch_level                = unknown                        (100/100)
fine_grained_label_available = false                         (100/100)
ground_truth_strength        = medium                        (100/100)  ← 全部相同
```

**`ground_truth_strength` 在 100 条里全是占位符 `medium`**，与同一行的 `retouch_level=unknown`、`fine_grained_label_available=false` 自相矛盾。

**绝对不能拿它当真值去训练或验证「修饰强度分类器」**——模型会学成「永远输出 medium」，而指标看起来还很漂亮。
这正是 shortcut risk 的来源。成员 3 在 `DATASET_CARD.md` 也写明「不得用它训练强度分类器」。

## 使用建议（评测技巧）

经典 CV 算法（MediaPipe 对齐 + 亮度/色温/高频能量比）**不需要训练**，因此**不需要 train/test 划分——
100 对全部可以当评测集用**。把 `originals/` 当 before、`retouched/` 当 after 喂给算法，看 `skin_texture` / `smoothing`
能否判出显著差异；若连这个都测不出，对真实数据更没用。产出的是真实可对外说的数字：
「100 对配对数据上检出率 X%，N 张困难负样本上误报率 Y%」。

## 许可

见 `../member2_forensics/FFHQR_LICENSE_NOTE.md`。FFHQR 为 CC BY-NC-SA 4.0，非商业。
