from pathlib import Path

from app.cache import SQLiteCache


def test_sqlite_cache_round_trip(tmp_path: Path):
    cache = SQLiteCache(tmp_path / "cache.sqlite3", ttl_seconds=3600)
    key = "abc"
    value = {"x": 1}
    cache.set(key, value)
    found = cache.get(key)
    assert found == value
