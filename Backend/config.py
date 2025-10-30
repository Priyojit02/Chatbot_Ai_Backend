"""
Centralized configuration for the Backend app.
- Loads from environment variables and optional app.royete (YAML-like) file.
- Provides typed settings via Pydantic BaseSettings.
- Exposes helpers for logging and CORS.
"""
from __future__ import annotations

import os
import json
from functools import lru_cache
from typing import List, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator
import yaml

# Ensure .env is loaded early
load_dotenv()


class CORSConfig(BaseModel):
    allow_origins: List[str] = Field(default_factory=lambda: ["*"])
    allow_methods: List[str] = Field(default_factory=lambda: ["GET", "POST", "OPTIONS"])
    allow_headers: List[str] = Field(default_factory=lambda: ["*"])
    allow_credentials: bool = True


class FastAPIConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = True
    workers: int = 1
    cors: CORSConfig = Field(default_factory=CORSConfig)


class LoggingConfig(BaseModel):
    level: str = "INFO"
    json_format: bool = False
    slow_request_threshold_ms: int = 1200


class SAPTimeouts(BaseModel):
    connect: int = 10
    read: int = 30


class SAPConfig(BaseModel):
    base_url: str = Field(default_factory=lambda: os.getenv("SAP_BASE_URL", "").rstrip("/"))
    username: str = Field(default_factory=lambda: os.getenv("SAP_USERNAME", ""))
    password: str = Field(default_factory=lambda: os.getenv("SAP_PASSWORD", ""))
    client: str = Field(default_factory=lambda: os.getenv("SAP_CLIENT", "").strip())
    telephone_entity: str = "TELEPHONEADDRSet"
    postal_entity: str = "PLANTPOSTALADDRSet"
    timeouts: SAPTimeouts = Field(default_factory=SAPTimeouts)


class LLMConfig(BaseModel):
    provider: str = "langchain-openai"
    default_model: str = "bedrock.anthropic.claude-opus-4"
    base_url: str = "https://genai-sharedservice-americas.pwcinternal.com"
    api_key_env: str = "OPENAI_API_KEY"
    temperature: float = 0.0
    max_tokens: Optional[int] = None
    request_timeout: int = 30
    streaming: bool = False


class AppMeta(BaseModel):
    app_name: str = "SAP Plant Conversational Hub"
    environment: str = Field(default_factory=lambda: os.getenv("APP_ENV", "dev"))
    version: str = "1.1"


class Settings(BaseModel):
    meta: AppMeta = Field(default_factory=AppMeta)
    fastapi: FastAPIConfig = Field(default_factory=FastAPIConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    sap: SAPConfig = Field(default_factory=SAPConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)

    @field_validator("sap")
    def _validate_sap(cls, v: SAPConfig) -> SAPConfig:
        # Don't hard fail here; allow app to start with placeholders.
        return v


def _load_yaml_config(path: str) -> dict:
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        try:
            return yaml.safe_load(f) or {}
        except Exception:
            return {}


def _env_override(cfg: dict) -> dict:
    """Optionally override select fields from env; keep simple to avoid surprises."""
    # Top-level shortcuts
    if os.getenv("APP_ENV"):
        cfg.setdefault("meta", {})["environment"] = os.getenv("APP_ENV")

    # SAP
    sap_cfg = cfg.setdefault("sap", {})
    for k_env, key in [
        ("SAP_BASE_URL", "base_url"),
        ("SAP_USERNAME", "username"),
        ("SAP_PASSWORD", "password"),
        ("SAP_CLIENT", "client"),
    ]:
        val = os.getenv(k_env)
        if val is not None:
            sap_cfg[key] = val

    # LLM
    llm_cfg = cfg.setdefault("llm", {})
    for k_env, key in [
        ("OPENAI_BASE_URL", "base_url"),
        ("OPENAI_MODEL", "default_model"),
    ]:
        val = os.getenv(k_env)
        if val is not None:
            llm_cfg[key] = val

    return cfg


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    base_cfg = _load_yaml_config(os.path.join(os.path.dirname(__file__), "app.royete"))
    merged = _env_override(base_cfg)
    # Pydantic will coerce nested dicts into typed models
    return Settings(**merged)


# ---- Helpers ---------------------------------------------------------------

def configure_logging(settings: Settings) -> None:
    import logging
    import sys

    handlers = []
    console = logging.StreamHandler(sys.stdout)
    handlers.append(console)

    logging.basicConfig(
        level=settings.logging.level.upper(),
        format=(
            "%(message)s"
            if settings.logging.json_format
            else "%(asctime)s %(levelname)s %(name)s - %(message)s"
        ),
        handlers=handlers,
    )


def build_cors(settings: Settings):
    from fastapi.middleware.cors import CORSMiddleware

    def add(app):
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.fastapi.cors.allow_origins,
            allow_methods=settings.fastapi.cors.allow_methods,
            allow_headers=settings.fastapi.cors.allow_headers,
            allow_credentials=settings.fastapi.cors.allow_credentials,
        )
        return app

    return add
