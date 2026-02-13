from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .models import PublisherDefinition, TopicDefinition

LOGGER = logging.getLogger(__name__)


@dataclass
class AppSettings:
    app_name: str
    version: str
    contact_email: str
    cache_ttl_hours: int
    request_timeout_sec: int
    max_retries: int
    backoff_base_sec: float
    max_records_default: int
    rows_per_request: int
    low_coverage_threshold: float
    topic_catalog_lookback_years: int
    gap_min_topic_cagr: float
    gap_max_target_share: float
    gap_min_topic_volume: int
    topics: list[TopicDefinition]
    publishers: list[PublisherDefinition]

    @property
    def user_agent(self) -> str:
        return f"{self.app_name}/{self.version} (mailto:{self.contact_email})"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "time": self.formatTime(record, self.datefmt),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging() -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_settings(config_root: Path) -> AppSettings:
    app_cfg = _read_yaml(config_root / "app.yaml").get("app", {})
    topics_cfg = _read_yaml(config_root / "topics.yaml").get("topics", [])
    publishers_cfg = _read_yaml(config_root / "publishers.yaml").get("publishers", [])

    settings = AppSettings(
        app_name=app_cfg.get("name", "Photonics Publishing Intelligence"),
        version=str(app_cfg.get("version", "0.1.0")),
        contact_email=app_cfg.get("contact_email", "contact@example.com"),
        cache_ttl_hours=int(app_cfg.get("cache_ttl_hours", 24)),
        request_timeout_sec=int(app_cfg.get("request_timeout_sec", 30)),
        max_retries=int(app_cfg.get("max_retries", 4)),
        backoff_base_sec=float(app_cfg.get("backoff_base_sec", 0.8)),
        max_records_default=int(app_cfg.get("max_records_default", 2000)),
        rows_per_request=int(app_cfg.get("rows_per_request", 200)),
        low_coverage_threshold=float(app_cfg.get("low_coverage_threshold", 0.25)),
        topic_catalog_lookback_years=int(app_cfg.get("topic_catalog_lookback_years", 5)),
        gap_min_topic_cagr=float(app_cfg.get("gap_analysis", {}).get("min_topic_cagr", 0.08)),
        gap_max_target_share=float(app_cfg.get("gap_analysis", {}).get("max_target_share", 0.12)),
        gap_min_topic_volume=int(app_cfg.get("gap_analysis", {}).get("min_topic_volume", 40)),
        topics=[TopicDefinition(**topic) for topic in topics_cfg],
        publishers=[PublisherDefinition(**publisher) for publisher in publishers_cfg],
    )
    LOGGER.info("Loaded settings: topics=%s publishers=%s", len(settings.topics), len(settings.publishers))
    return settings
