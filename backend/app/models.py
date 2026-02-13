from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class TopicDefinition(BaseModel):
    key: str
    name: str
    keywords: list[str] = Field(default_factory=list)
    synonyms: list[str] = Field(default_factory=list)
    negative_keywords: list[str] = Field(default_factory=list)


class PublisherDefinition(BaseModel):
    name: str
    aliases: list[str] = Field(default_factory=list)
    prefixes: list[str] = Field(default_factory=list)


class CoverageMetrics(BaseModel):
    total_records: int
    abstract_rate: float
    affiliation_rate: float
    accepted_date_rate: float
    issued_date_rate: float


class AnalyzeRequest(BaseModel):
    topic_key: str | None = None
    ad_hoc_query: str | None = None
    from_pub_date: date = date(2018, 1, 1)
    until_pub_date: date = Field(default_factory=date.today)
    doc_types: list[str] = Field(default_factory=lambda: ["journal-article", "proceedings-article"])
    publishers: list[str] = Field(default_factory=list)
    container_titles: list[str] = Field(default_factory=list)
    doi_prefixes: list[str] = Field(default_factory=list)
    max_records: int | None = None
    rows_per_request: int | None = None
    refresh_cache: bool = False
    include_global_baseline: bool = False


class ComparePublishersRequest(AnalyzeRequest):
    publishers: list[str]


class EmergingTopicsRequest(BaseModel):
    from_pub_date: date = date(2018, 1, 1)
    until_pub_date: date = Field(default_factory=date.today)
    lookback_years: int | None = None
    max_records_per_topic: int | None = None
    refresh_cache: bool = False


class GapAnalysisRequest(EmergingTopicsRequest):
    target_publisher: str = "SPIE"


class TimeToPubRequest(AnalyzeRequest):
    metric: str = "created_to_published"


class ApiMeta(BaseModel):
    generated_at: str
    cached_responses: int
    live_responses: int
    last_api_call_at: str | None
    warnings: list[str] = Field(default_factory=list)


class QueryExport(BaseModel):
    endpoint: str
    payload: dict[str, Any]
