# FFHQ–FFHQR 100 对配对原型数据集 v1

## 结论

该数据集含 `100` 对已校验的 Before/After 图片，可直接用于原型阶段的二分类修饰检测、配对变化分析和数据读取流程验证。

## 数据结构

```text
FFHQ_FFHQR_100_pairs_v1/
├─ originals/              # FFHQ 官方原图，class_id=0
├─ retouched/              # FFHQR 专业修饰图，class_id=1
├─ splits/                 # train 80 / validation 10 / test 10
├─ paired_manifest.csv     # 一行一对，适合 Before/After 任务
├─ sample_manifest.csv     # 一行一张，适合二分类
├─ official_source_metadata.json
├─ dataset_summary.json
├─ paired_dataset.py       # PyTorch 配对数据读取示例
└─ errors.csv
```

## 校验结果

- 有效配对：100
- 错误或缺失：0
- 原图与修饰图字节完全相同：0
- 分辨率：全部 1024×1024 PNG
- FFHQ 原图：已逐张通过 NVIDIA 官方 MD5 校验
- 配对依据：FFHQ 与 FFHQR 共享的官方数字编号

## 标签边界

FFHQR 只能支持 `original` 与 `generic_professional_retouch` 标签。它不提供磨皮、美白、瘦脸等单项操作的真值，也没有 Low/Medium/High 强度真值。

因此，不得把本数据集直接标注成“磨皮”，也不得用它单独训练修饰强度分类器。

## 适合的任务

- 专业修饰二分类原型；
- Before/After 皮肤纹理、颜色和频域变化分析；
- 数据加载、接口和评测脚本联调；
- 后续模型的外部小规模评测。

## 不建议直接宣称

- 不要宣称这 100 对能代表真实社交媒体的所有磨皮/滤镜情况；
- 不要从 FFHQR 标签推断具体修饰类型或强度；
- 原型 80/10/10 划分只用于跑通流程，完整数据应恢复 FFHQR 官方划分。

## 许可说明

FFHQ 单张图片许可信息保存在 `paired_manifest.csv` 与 `official_source_metadata.json` 中。FFHQR 修饰数据为 CC BY-NC-SA 4.0，项目应用需遵守非商业使用、署名和相同方式共享等要求。
