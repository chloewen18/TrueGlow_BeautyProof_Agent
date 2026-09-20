# 成员 3 → 成员 1 对接说明

我交付的是 `beauty_effect_attribution` Tool，不是新的 Main Agent。请 Main Agent 根据用户上传内容选择调用：

- 只有一张图：调用 `analyze_single`。
- 有 Before/After：调用 `analyze_pair`。
- 同时有前景 mask：传给 `analyze_pair`；没有 mask 也能运行，但要保留可靠性警告。

推荐以独立 HTTP 服务方式接入：

```bash
pip install -r requirements-api.txt
uvicorn api:app --host 0.0.0.0 --port 8003
```

Main Agent 稳定依赖的字段只有：`schema_version`、`tool`、`request_id`、`status`、`result`、`evidence`和 `limitations`。

请勿直接向用户展示“造假/没造假”。建议 Main Agent 输出：

> 检测到若干修饰或拍摄条件差异，因此该内容中的妆效不宜全部归因于产品。结论为辅助风险提示，仍需结合原始素材和创作者补证。

如果 Main Agent 需要统一风险等级，可直接使用 `comparison_reliability` 的 `low / medium / high`，不要根据未校准的单个概率自由生成因果百分比。
