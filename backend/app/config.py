"""应用配置：环境变量驱动，全部有默认值，Mock 模式可离线运行。"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 服务
    app_host: str = "127.0.0.1"
    app_port: int = 8000

    # LLM 解释层: mock | deepseek
    llm_provider: str = "mock"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"
    llm_timeout_seconds: int = 60

    # 存储与日志
    data_dir: str = "./data"
    log_level: str = "INFO"

    @property
    def resolved_data_dir(self) -> Path:
        p = Path(self.data_dir)
        if not p.is_absolute():
            p = BASE_DIR / p
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def evidence_dir(self) -> Path:
        d = self.resolved_data_dir / "evidence"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def logs_dir(self) -> Path:
        d = self.resolved_data_dir / "logs"
        d.mkdir(parents=True, exist_ok=True)
        return d


settings = Settings()
