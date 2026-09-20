# 项目目录

| 路径 | 用途 |
| --- | --- |
| `app.py` | Streamlit 工作台入口 |
| `api/` | 前端页面、客户端与静态模拟支持；主后端为 `backend.app.main:app` |
| `backend/app/agent/` | 规划、路由、融合、分级与报告生成 |
| `backend/app/tools/` | 来源、取证、对比与文本工具 |
| `backend/app/integrations/` | 主应用调用的模型、OCR 和规则实现 |
| `backend/app/paths.py` | 模型配套资源的路径配置 |
| `backend/demo/`、`examples/`、`data/mock/` | 明确标注的模拟案例与报告示例 |
| `member2_forensics/deliverables/` | 取证评测输出；`legacy_simulated/` 仍供模拟接口与测试使用 |
| `member3_dataset/deliverables/v1_1/` | 模型清单、接口约定与训练评测资料 |
| `member4_text/deliverables/` | 词典、功效证据、测试表与参考程序；v1 中部分资源仍被使用 |
| `data/datasets/` | 配对数据、数据卡与样本清单 |
| `data/models/` | 本地模型权重，不提交 |
| `data/integrated_evaluation.json`、`data/member4_evaluation.json` | 评测结果及适用范围 |
| `backend/data/` | 上传文件、证据与运行日志，不提交 |
| `data/volunteers/`、`data/evaluation_runs/` | 本地采集材料与逐轮评测，不提交 |
| `data_generation/` | 数据标注与困难负样本辅助工具 |
| `schemas/` | 共享 JSON Schema |
| `scripts/`、`tests/` | 启动、评测与验证 |
| `vendor/trufor/` | 第三方源码和许可证 |

安装入口见[本地部署](LOCAL_DEPLOYMENT.md)。修改应用逻辑时编辑 `backend/app/` 中的实现；模型配套资源及原始评测报告保留来源和指标口径。
