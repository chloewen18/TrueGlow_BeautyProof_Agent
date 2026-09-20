# 成员4：文本、评论与功效证据

- 当前交付：[deliverables/v2](deliverables/v2/)，含新版词典、功效证据及原始程序。
- 初版材料：[deliverables/v1](deliverables/v1/)，其中测试题、解释模板和评论参考仍被主应用使用，不能删除。
- 实际集成代码：`../backend/app/integrations/member4/`。包含中文路径与本地 OCR 兼容修复，不要直接用交付副本覆盖。
- API：`../backend/app/member4_api.py`；页面：`../api/member4_ui.py`。
- 路径配置：`../backend/app/paths.py`。

在项目根目录独立运行：

```powershell
.venv/Scripts/python.exe -m backend.app.integrations.member4.full_pipeline --image member4_text/deliverables/v2/demo/test.PNG --out backend/data/member4_pipeline.json
```

原20/30题成绩只验证规范化宣称集合，已经用于迭代，不是新的独立盲测。功效来源是交付资料，未在线复核。
