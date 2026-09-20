# TrueGlow 映真 —— 单容器同时运行 Streamlit 前端与 FastAPI 后端
# 适配 Hugging Face Spaces（Docker SDK，默认端口 7860）
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    # 运行时数据写到可写目录，避免依赖镜像内目录权限
    DATA_DIR=/tmp/trueglow-data \
    # 前端指向同容器内的后端
    BEAUTYPROOF_API_BASE_URL=http://127.0.0.1:8000 \
    BEAUTYPROOF_USE_MOCK=false

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends supervisor \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /tmp/trueglow-data

# HF Spaces 默认监听 7860；本机可用 -p 7860:7860
EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status==200 else 1)"

CMD ["supervisord", "-c", "/app/deploy/supervisord.conf"]
