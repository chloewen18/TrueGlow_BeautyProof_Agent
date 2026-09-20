# 成员 3 集成说明（Main Agent 侧 / A 维护）

把成员 3 的 `beauty_effect_attribution` 服务接入 TrueGlow 主链路。
**默认关闭**，关闭时 `image_forensics` 与 `before_after` 仍走原有 mock，行为完全不变。

---

## 一、目录

| 文件 | 作用 |
|---|---|
| `client.py` | HTTP 客户端：健康检查、超时、MediaRef 解析（本地路径 / URL） |
| `adapter.py` | 字段归一与语义映射（成员 3 契约 → 本项目 evidence schema） |
| `handlers.py` | ToolHandler：real 优先，失败自动降级到原 mock |
| `selftest.py` | 离线自检，**不需要启动成员 3 服务** |

---

## 二、启用步骤

### 1. 启动成员 3 的服务（独立进程）

```bash
cd "Member3 检测模型_v1"
pip install -r requirements-api.txt
uvicorn api:app --host 127.0.0.1 --port 8003
curl http://127.0.0.1:8003/health
# 期望: {"status":"ok","tool":"beauty_effect_attribution","schema_version":"1.0.0"}
```

模型依赖 torch 2.8 / torchvision 0.23，**不要装进主工程环境**，用独立 venv。

### 2. 配置 Main Agent

`backend/.env`（或环境变量）：

```bash
MEMBER3_ENABLED=true
MEMBER3_BASE_URL=http://127.0.0.1:8003
MEMBER3_TIMEOUT_SECONDS=60
```

### 3. 启动 Main Agent

```bash
cd backend
uvicorn app.main:app --port 8000
curl http://127.0.0.1:8000/
# member3_tools 应为 ["image_forensics", "before_after"]
```

---

## 三、自检

```bash
cd backend
python -m app.integrations.member3.selftest
```

覆盖 9 组断言：方向转换、大小写归一、Unknown 兜底、分级阈值、磨皮对比。**改 adapter.py 后必须重跑。**

---

## 四、字段映射

### 单图 `analyze_single` → T3 `ImageForensicsEvidence`

| 成员 3 | 本项目 | 说明 |
|---|---|---|
| `generic_retouch.score` | `integrity_score = 1 - score` | ⚠️ **方向转换**，成员 3 越高越像修图，本项目越高越完整 |
| `operations.smoothing` | `skin_smoothing` / `texture_loss` | 强度档 0/30/60/90 → Low/Low/Medium/High；纹理损失是磨皮的代理 |
| `operations.whitening` | `whitening` | F1 仅 60.7%，仅辅助 |
| `operations.facelifting` | `face_reshape` | |
| （无） | `splicing` / `inpainting` / `local_replacement` / `ai_generated` = **Unknown** | 成员 3 不做这些；未检测 ≠ 没有，故不用 Not detected |

### 前后对比 `analyze_pair` → T4 `BeforeAfterEvidence`

| 成员 3 | 本项目 dimension | Similar / Different / Significant |
|---|---|---|
| `parameter_deltas.exposure` | `exposure` | 0.10 / 0.25 EV |
| `temperature` + `tint` | `white_balance` | 150K·2 / 400K·5 |
| `contrast|highlights|shadows|whites|blacks|saturation|vibrance` 最大者 | `tone` | 5 / 15 |
| `parameter_deltas.texture` | `skin_texture` | 0.2 / 0.5（尺度待标定） |
| 两张单图 smoothing 概率差 | `smoothing` | 0.05 / 0.20 |
| （成员 3 不提供） | `face_angle` / `crop` = **Unknown** | 不得默认 Similar |

`comparison_reliability` → `attribution_strength`：High→Strong、Medium→Moderate、Low→Weak、Unknown→Unknown。

---

## 五、降级规则

出现下列任一情况自动回落原 mock，并在 `meta.warnings` 写明原因：

- 服务未启用 / 未启动 / 超时
- 响应缺 `schema_version|tool|status|result|evidence|limitations`
- `status != "ok"`
- `MediaRef.ref` 解析不出本地文件
- `task=forensics`（超出成员 3 能力范围）
- payload 缺 `images` 或 `before/after`

`meta.model` 会变成 `mock(fallback: <原因>)`，前端据此显示「模拟」徽章。
**降级不是静默的**——任何一次 mock 数据都会留下痕迹。

---

## 六、已知限制

1. **Stage 3 change_probabilities 不参与判定**（真实负样本 FPR 98.8%~100%）。
2. **Stage 2 跨域不可用**：PPR10K 上 F1 41.4%、FPR 35.9%，只在单图模式用其细粒度信号。
3. **分级阈值是启发式的**，等成员 3 交出困难负样本集后需重新标定（`adapter.py` 顶部常量）。
4. `EvidenceReliability` 只有三值，成员 3 的 `Unknown` 映射为 `Low` + `attribution_strength=Unknown` 组合表达。
5. `_pending_warnings` 为实例属性，**并发场景需改为 contextvar**（当前 demo 串行执行）。

契约待办见《成员 3 对接反馈 v1》第三节（成员 3 出 v1.1 后可简化本适配层）。
