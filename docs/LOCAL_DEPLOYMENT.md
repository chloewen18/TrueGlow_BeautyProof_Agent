# 本地启动

所有命令均在项目根目录执行。
模型、数据集和私人数据不应自动提交或公开上传。

## 已有环境

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_local.ps1
```

前端：http://127.0.0.1:8503/ 。API 文档：http://127.0.0.1:8000/docs 。
脚本仅绑定本机并使用隐藏窗口，日志在 `backend/data/runtime/`。
若已有服务，请直接访问；若需第二套服务，使用：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_local.ps1 -ApiPort 8001 -UiPort 8504
```

## 新机器安装

已验证环境为 Windows + Python 3.12，其他平台需另行测试。

```powershell
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-verified-win-py312.txt
```

`requirements.txt`、`requirements-models.txt`、`requirements-ocr.txt` 是分模块依赖说明；冻结文件用于复现已验证环境。
安装依赖不会自动获得模型权重与数据集，需经授权单独准备 `data/models/` 与 `data/datasets/`。
TruFor源码在 `vendor/trufor/`，权重单独放 `data/models/trufor.pth.tar`。
修饰模型还需将 `member3_dataset/deliverables/v1_1/MODEL_MANIFEST.json` 复制到 `data/models/MODEL_MANIFEST.json`，供加载时校验权重。

成员交付路径集中于 `backend/app/paths.py`，具体资源位置参见三个成员目录的 README。

## 验证与评测

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -p 'test_*.py'
.venv/Scripts/python.exe scripts/check_end_to_end.py
.venv/Scripts/python.exe scripts/evaluate_integrated.py --member3-pairs 100 --trufor-live
```

端到端验证需要 API 启动；完整评测会写入新的逐样本记录并更新最近结果。CPU推理较慢，不建议并行发起多轮评测。
评测范围与限制见 `docs/DATASET_AND_EVAL.md`。

## 运行边界

- 主后端是 `backend.app.main:app`，不是历史模拟服务 `api/server.py`。
- 主应用已接入真实本地取证、修饰检测、规则分析与 OCR；模拟案例必须明确标识，失败不使用假数据补位。
- C2PA 验证和产品因果归因尚未实现，Unknown 不表示真实或无风险。
- 前端 API 地址可通过 `BEAUTYPROOF_API_BASE_URL` 配置。旧 `BEAUTYPROOF_USE_MOCK=true` 仅用于明确的静态演示。
- 当前没有公网访问所需的完整身份认证与数据隔离，不要直接映射公网端口收集人脸图片。
