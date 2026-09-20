# 成员3：配对数据、修饰检测与条件比较

- 当前 v1.1 原始交付：[deliverables/v1_1](deliverables/v1_1/)。
- 原始接口说明：[interface_original.md](interface_original.md)。保留原文，实际返回结构以集成实现为准。
- 实际模型适配器：`../backend/app/integrations/member3/`。
- 前后对比入口：`../backend/app/tools/before_after.py`；差异图：`../backend/app/integrations/visual.py`。
- 配对数据：`../data/datasets/FFHQ_FFHQR_100_pairs_v1/`，不重复复制到此目录。
- 本地权重：`../data/models/member3/`，不入库。
- 评测：`../scripts/evaluate_integrated.py`；当前结果：`../data/integrated_evaluation.json`。

100对只做探索性复测，尚未排除训练重叠。占位强度不是真值，差异图不证明操作类型，模型输出不证明产品因果贡献。
