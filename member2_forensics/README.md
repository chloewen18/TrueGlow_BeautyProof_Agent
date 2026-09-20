# 成员2：来源溯源与通用取证

- 当前原始交付：[deliverables/v2](deliverables/v2/)。包含交付报告和 NPZ，不等同于全部在本机重新推理。
- 历史模拟材料：[deliverables/legacy_simulated](deliverables/legacy_simulated/)。只用于兼容测试，禁止作为真实评测。
- 实际集成代码：`../backend/app/integrations/visual.py`、`../backend/app/integrations/metadata_parser.py`。
- 官方源码：`../vendor/trufor/`；本地权重：`../data/models/trufor.pth.tar`，不入库。
- 当前工具入口：`../backend/app/tools/image_forensics.py`、`../backend/app/tools/source_trace.py`。
- 评测：`../scripts/evaluate_integrated.py`；当前结果：`../data/integrated_evaluation.json`。

分数越高越可疑；完整性分数为 `1 - trufor_score`。低分不能排除美白、磨皮等细微修饰。
修改接入实现时应编辑实际集成代码，不要只编辑交付包副本。
