#!/usr/bin/env bash
# 本地（macOS / Linux）同时启动后端与前端。
# 与 deploy/supervisord.conf 中容器内运行的两条命令保持一致，便于本地验证。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="${PYTHON:-python3}"
API_PORT="${API_PORT:-8000}"
UI_PORT="${UI_PORT:-7860}"

# 前端默认指向本机后端；前后端分开部署时用环境变量覆盖
export BEAUTYPROOF_API_BASE_URL="${BEAUTYPROOF_API_BASE_URL:-http://127.0.0.1:${API_PORT}}"

API_PID=""
UI_PID=""
cleanup() {
  [ -n "$UI_PID" ] && kill "$UI_PID" 2>/dev/null || true
  [ -n "$API_PID" ] && kill "$API_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

"$PY" -m uvicorn backend.app.main:app --host 127.0.0.1 --port "$API_PORT" &
API_PID=$!

"$PY" -m streamlit run app.py \
  --server.address 0.0.0.0 --server.port "$UI_PORT" \
  --server.headless true --browser.gatherUsageStats false &
UI_PID=$!

echo "工作台:   http://127.0.0.1:${UI_PORT}/"
echo "API 文档: http://127.0.0.1:${API_PORT}/docs   （健康检查 /healthz）"
echo "按 Ctrl+C 停止。"

wait
