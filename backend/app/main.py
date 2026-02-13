from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .analysis import (
    apply_topic_filter,
    compare_publishers,
    coverage_metrics,
    emerging_topics,
    gap_analysis,
    institutions_breakdown,
    journal_intelligence,
    time_to_pub,
    topic_overview,
)
from .cache import SQLiteCache
from .config import AppSettings, configure_logging, load_settings
from .crossref import CrossrefClient
from .models import AnalyzeRequest, ApiMeta, ComparePublishersRequest, EmergingTopicsRequest, GapAnalysisRequest, TimeToPubRequest

configure_logging()

def _default_user_data_dir() -> Path:
    if os.name == "nt":
        base = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.getenv("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return base / "PhotonicsPublishingIntelligence"


def _resolve_paths() -> tuple[Path, Path]:
    project_root = Path(__file__).resolve().parents[2]
    bundled_root = Path(getattr(sys, "_MEIPASS", project_root))

    config_dir = Path(os.getenv("PHOTONICS_CONFIG_DIR", str(bundled_root / "config")))
    if not config_dir.exists():
        config_dir = project_root / "config"

    cache_path_env = os.getenv("PHOTONICS_CACHE_PATH")
    if cache_path_env:
        cache_path = Path(cache_path_env)
    elif getattr(sys, "frozen", False):
        cache_path = _default_user_data_dir() / "cache.sqlite3"
    else:
        cache_path = project_root / "backend" / "cache.sqlite3"
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    return config_dir, cache_path


CONFIG_DIR, CACHE_PATH = _resolve_paths()
SETTINGS: AppSettings = load_settings(CONFIG_DIR)
CACHE = SQLiteCache(CACHE_PATH, ttl_seconds=SETTINGS.cache_ttl_hours * 3600)
CLIENT = CrossrefClient(SETTINGS, CACHE)

app = FastAPI(title=SETTINGS.app_name, version=SETTINGS.version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await CLIENT.close()


def _topic_lookup(topic_key: str | None):
    if not topic_key:
        return None
    for topic in SETTINGS.topics:
        if topic.key == topic_key:
            return topic
    return None


def _publisher_prefixes(selected_publishers: list[str]) -> tuple[list[str], list[str]]:
    names = []
    prefixes = []
    if not selected_publishers:
        return names, prefixes
    selected_lower = {s.lower() for s in selected_publishers}
    for pub in SETTINGS.publishers:
        options = {pub.name.lower(), *[alias.lower() for alias in pub.aliases]}
        if selected_lower.intersection(options):
            names.append(pub.name)
            prefixes.extend(pub.prefixes)
    unresolved = [p for p in selected_publishers if p.lower() not in {n.lower() for n in names}]
    names.extend(unresolved)
    return names, sorted(set(prefixes))


def _matches_publisher(item_publisher: str, selected: list[str]) -> bool:
    if not selected:
        return True
    item_l = (item_publisher or "").lower()
    for name in selected:
        if name.lower() in item_l:
            return True
    return False


def _post_filter_records(
    records: list[dict[str, Any]],
    *,
    doc_types: list[str],
    publishers: list[str],
    prefixes: list[str],
    container_titles: list[str],
) -> list[dict[str, Any]]:
    doc_types_set = {d.lower() for d in doc_types}
    prefixes_set = {p.lower() for p in prefixes}
    container_set = {c.lower() for c in container_titles}

    out: list[dict[str, Any]] = []
    for item in records:
        if doc_types_set and (item.get("type") or "").lower() not in doc_types_set:
            continue
        if publishers and not _matches_publisher(item.get("publisher") or "", publishers):
            continue
        if prefixes_set:
            doi = (item.get("DOI") or "").lower()
            if not any(doi.startswith(prefix + "/") or doi.startswith(prefix) for prefix in prefixes_set):
                continue
        if container_set:
            container = " ".join(item.get("container-title") or []).lower()
            if not any(term in container for term in container_set):
                continue
        out.append(item)
    return out


def _meta(warnings: list[str] | None = None) -> ApiMeta:
    return ApiMeta(
        generated_at=datetime.now(timezone.utc).isoformat(),
        cached_responses=CLIENT.stats.cached_responses,
        live_responses=CLIENT.stats.live_responses,
        last_api_call_at=CLIENT.stats.last_api_call_at,
        warnings=warnings or [],
    )


async def _fetch_records(payload: AnalyzeRequest) -> list[dict[str, Any]]:
    publisher_names, prefixes_from_publishers = _publisher_prefixes(payload.publishers)
    prefixes = sorted(set(payload.doi_prefixes + prefixes_from_publishers))
    topic = _topic_lookup(payload.topic_key)
    search_query = payload.ad_hoc_query or (" OR ".join(topic.keywords[:3]) if topic else None)

    records = await CLIENT.fetch_works(
        query=search_query,
        from_pub_date=payload.from_pub_date.isoformat(),
        until_pub_date=payload.until_pub_date.isoformat(),
        doc_types=payload.doc_types[:1],
        publisher_names=publisher_names[:1],
        prefixes=prefixes[:1],
        container_titles=payload.container_titles[:1],
        max_records=payload.max_records or SETTINGS.max_records_default,
        rows=payload.rows_per_request or SETTINGS.rows_per_request,
        refresh_cache=payload.refresh_cache,
    )

    records = _post_filter_records(
        records,
        doc_types=payload.doc_types,
        publishers=publisher_names,
        prefixes=prefixes,
        container_titles=payload.container_titles,
    )
    filtered, _ = apply_topic_filter(records, topic, payload.ad_hoc_query)
    return filtered


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "app": SETTINGS.app_name, "version": SETTINGS.version}


@app.get("/api/config")
async def get_config() -> dict[str, Any]:
    return {
        "app": {
            "name": SETTINGS.app_name,
            "version": SETTINGS.version,
            "max_records_default": SETTINGS.max_records_default,
            "rows_per_request": SETTINGS.rows_per_request,
            "low_coverage_threshold": SETTINGS.low_coverage_threshold,
        },
        "topics": [topic.model_dump() for topic in SETTINGS.topics],
        "publishers": [publisher.model_dump() for publisher in SETTINGS.publishers],
    }


@app.post("/api/analyze/topic")
async def analyze_topic(payload: AnalyzeRequest) -> dict[str, Any]:
    records = await _fetch_records(payload)
    coverage = coverage_metrics(records)
    warnings = []
    if coverage.abstract_rate < SETTINGS.low_coverage_threshold:
        warnings.append("Low abstract coverage; topic relevance may be undercounted.")
    if coverage.affiliation_rate < SETTINGS.low_coverage_threshold:
        warnings.append("Low affiliation coverage; institution rankings may be incomplete.")
    return {
        "query": payload.model_dump(mode="json"),
        "record_count": len(records),
        "coverage": coverage.model_dump(),
        "overview": topic_overview(records, settings=SETTINGS),
        "journals": journal_intelligence(records),
        "meta": _meta(warnings).model_dump(),
    }


@app.post("/api/analyze/compare_publishers")
async def analyze_compare_publishers(payload: ComparePublishersRequest) -> dict[str, Any]:
    records = await _fetch_records(payload)
    coverage = coverage_metrics(records)
    result = compare_publishers(records, payload.publishers, settings=SETTINGS)
    return {
        "query": payload.model_dump(mode="json"),
        "record_count": len(records),
        "coverage": coverage.model_dump(),
        "comparison": result,
        "meta": _meta().model_dump(),
    }


@app.post("/api/analyze/emerging_topics")
async def analyze_emerging_topics(payload: EmergingTopicsRequest) -> dict[str, Any]:
    records_by_topic: dict[str, list[dict[str, Any]]] = {}
    for topic in SETTINGS.topics:
        req = AnalyzeRequest(
            topic_key=topic.key,
            ad_hoc_query=" OR ".join(topic.keywords[:3]),
            from_pub_date=payload.from_pub_date,
            until_pub_date=payload.until_pub_date,
            max_records=payload.max_records_per_topic or min(SETTINGS.max_records_default, 1200),
            refresh_cache=payload.refresh_cache,
        )
        records_by_topic[topic.key] = await _fetch_records(req)

    return {
        "query": payload.model_dump(mode="json"),
        "result": emerging_topics(records_by_topic, SETTINGS.topics, lookback_years=payload.lookback_years or SETTINGS.topic_catalog_lookback_years),
        "meta": _meta().model_dump(),
    }


@app.post("/api/analyze/gap_analysis")
async def analyze_gap(payload: GapAnalysisRequest) -> dict[str, Any]:
    records_by_topic: dict[str, list[dict[str, Any]]] = {}
    for topic in SETTINGS.topics:
        req = AnalyzeRequest(
            topic_key=topic.key,
            ad_hoc_query=" OR ".join(topic.keywords[:3]),
            from_pub_date=payload.from_pub_date,
            until_pub_date=payload.until_pub_date,
            max_records=payload.max_records_per_topic or min(SETTINGS.max_records_default, 1200),
            refresh_cache=payload.refresh_cache,
        )
        records_by_topic[topic.key] = await _fetch_records(req)

    return {
        "query": payload.model_dump(mode="json"),
        "result": gap_analysis(records_by_topic, payload.target_publisher, SETTINGS, SETTINGS.topics),
        "meta": _meta().model_dump(),
    }


@app.post("/api/analyze/institutions")
async def analyze_institutions(payload: AnalyzeRequest) -> dict[str, Any]:
    records = await _fetch_records(payload)
    coverage = coverage_metrics(records)
    warnings = []
    if coverage.affiliation_rate < SETTINGS.low_coverage_threshold:
        warnings.append("Low affiliation coverage; institution trends are best-effort only.")
    return {
        "query": payload.model_dump(mode="json"),
        "record_count": len(records),
        "coverage": coverage.model_dump(),
        "institutions": institutions_breakdown(records),
        "meta": _meta(warnings).model_dump(),
    }


@app.post("/api/analyze/time_to_pub")
async def analyze_time_to_pub(payload: TimeToPubRequest) -> dict[str, Any]:
    records = await _fetch_records(payload)
    coverage = coverage_metrics(records)
    warnings = []
    if coverage.accepted_date_rate < SETTINGS.low_coverage_threshold:
        warnings.append("Accepted-date coverage is low; accepted->published lag may be unstable.")
    return {
        "query": payload.model_dump(mode="json"),
        "record_count": len(records),
        "coverage": coverage.model_dump(),
        "time_to_publication": time_to_pub(records),
        "meta": _meta(warnings).model_dump(),
    }
