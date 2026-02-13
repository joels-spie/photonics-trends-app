from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from .cache import SQLiteCache
from .config import AppSettings

LOGGER = logging.getLogger(__name__)

CROSSREF_BASE_URL = "https://api.crossref.org"


@dataclass
class ApiStats:
    cached_responses: int = 0
    live_responses: int = 0
    last_api_call_at: str | None = None


def build_filter_string(
    *,
    from_pub_date: str,
    until_pub_date: str,
    doc_types: list[str],
    publisher_names: list[str],
    prefixes: list[str],
    container_titles: list[str],
) -> str:
    filters: list[str] = [f"from-pub-date:{from_pub_date}", f"until-pub-date:{until_pub_date}"]
    if doc_types:
        filters.append(f"type:{doc_types[0]}")
    if prefixes:
        filters.append(f"prefix:{prefixes[0]}")
    if container_titles:
        filters.append(f"container-title:{container_titles[0]}")
    return ",".join(filters)


class CrossrefClient:
    def __init__(self, settings: AppSettings, cache: SQLiteCache):
        self.settings = settings
        self.cache = cache
        self.stats = ApiStats()
        self._client = httpx.AsyncClient(
            base_url=CROSSREF_BASE_URL,
            timeout=settings.request_timeout_sec,
            headers={"User-Agent": settings.user_agent},
        )

    async def close(self) -> None:
        await self._client.aclose()

    def _cache_key(self, path: str, params: dict[str, Any]) -> str:
        raw = json.dumps({"path": path, "params": params}, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    async def _get(self, path: str, params: dict[str, Any], refresh_cache: bool = False) -> dict[str, Any]:
        key = self._cache_key(path, params)
        if not refresh_cache:
            cached = self.cache.get(key)
            if cached is not None:
                self.stats.cached_responses += 1
                return cached

        for attempt in range(self.settings.max_retries + 1):
            resp = await self._client.get(path, params=params)
            self.stats.last_api_call_at = datetime.now(timezone.utc).isoformat()
            if resp.status_code == 200:
                payload = resp.json()
                self.cache.set(key, payload)
                self.stats.live_responses += 1
                return payload

            if resp.status_code in (429, 500, 502, 503, 504):
                retry_after = resp.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else self.settings.backoff_base_sec * (2 ** attempt)
                await asyncio.sleep(delay)
                continue
            if resp.status_code == 400:
                raise RuntimeError(f"Crossref rejected query params: {resp.text}")
            resp.raise_for_status()

        raise RuntimeError("Crossref request failed after retries")

    async def fetch_works(
        self,
        *,
        query: str | None,
        from_pub_date: str,
        until_pub_date: str,
        doc_types: list[str],
        publisher_names: list[str],
        prefixes: list[str],
        container_titles: list[str],
        max_records: int,
        rows: int,
        refresh_cache: bool,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        cursor = "*"
        while len(items) < max_records and cursor:
            params = {
                "query": query or None,
                "filter": build_filter_string(
                    from_pub_date=from_pub_date,
                    until_pub_date=until_pub_date,
                    doc_types=doc_types,
                    publisher_names=publisher_names,
                    prefixes=prefixes,
                    container_titles=container_titles,
                ),
                "rows": min(rows, max_records - len(items)),
                "cursor": cursor,
            }
            payload = await self._get("/works", params=params, refresh_cache=refresh_cache)
            message = payload.get("message", {})
            page_items = message.get("items", [])
            if not page_items:
                break
            items.extend(page_items)
            next_cursor = message.get("next-cursor")
            if not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor
        LOGGER.info("Fetched records from Crossref: %s", len(items))
        return items
