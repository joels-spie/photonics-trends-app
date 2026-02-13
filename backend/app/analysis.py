from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from datetime import date
from html import unescape
from typing import Any

from .config import AppSettings
from .models import CoverageMetrics, TopicDefinition
from .topic_matcher import TopicMatcher, ad_hoc_match_score

_TAG_RE = re.compile(r"<[^>]+>")
_NON_WORD = re.compile(r"[^a-z0-9 ]+")


def _date_from_parts(parts: list[int] | None) -> date | None:
    if not parts:
        return None
    y = parts[0]
    m = parts[1] if len(parts) > 1 else 1
    d = parts[2] if len(parts) > 2 else 1
    try:
        return date(int(y), int(m), int(d))
    except ValueError:
        return None


def _extract_date(item: dict[str, Any], *keys: str) -> date | None:
    for key in keys:
        section = item.get(key)
        if not section:
            continue
        parts = (section.get("date-parts") or [[None]])[0]
        result = _date_from_parts(parts)
        if result:
            return result
    return None


def get_published_date(item: dict[str, Any]) -> date | None:
    return _extract_date(item, "issued", "published-online", "published-print", "created")


def get_accepted_date(item: dict[str, Any]) -> date | None:
    return _extract_date(item, "accepted")


def get_created_date(item: dict[str, Any]) -> date | None:
    return _extract_date(item, "created", "deposited")


def _strip_abstract(value: str | None) -> str:
    if not value:
        return ""
    return _TAG_RE.sub(" ", unescape(value))


def record_text(item: dict[str, Any]) -> str:
    title = " ".join(item.get("title") or [])
    abstract = _strip_abstract(item.get("abstract"))
    container = " ".join(item.get("container-title") or [])
    return f"{title} {abstract} {container}".strip()


def _norm_inst(name: str) -> str:
    value = _NON_WORD.sub(" ", name.lower()).strip()
    return re.sub(r"\s+", " ", value)


def _extract_country(affiliation_name: str) -> str | None:
    parts = [p.strip() for p in affiliation_name.split(",") if p.strip()]
    if len(parts) < 2:
        return None
    last = parts[-1]
    if len(last) in (2, 3) or len(last.split()) <= 3:
        return last
    return None


def coverage_metrics(records: list[dict[str, Any]]) -> CoverageMetrics:
    total = len(records)
    if total == 0:
        return CoverageMetrics(total_records=0, abstract_rate=0.0, affiliation_rate=0.0, accepted_date_rate=0.0, issued_date_rate=0.0)
    abstract = sum(1 for r in records if bool(r.get("abstract")))
    affiliation = 0
    accepted = 0
    issued = 0
    for item in records:
        authors = item.get("author") or []
        if any(a.get("affiliation") for a in authors):
            affiliation += 1
        if get_accepted_date(item):
            accepted += 1
        if get_published_date(item):
            issued += 1
    return CoverageMetrics(total_records=total, abstract_rate=abstract / total, affiliation_rate=affiliation / total, accepted_date_rate=accepted / total, issued_date_rate=issued / total)


def _cagr(first: float, last: float, periods: int) -> float | None:
    if first <= 0 or last <= 0 or periods <= 0:
        return None
    return (last / first) ** (1 / periods) - 1


def _yoy_series(per_year: dict[int, int]) -> list[dict[str, float | int | None]]:
    years = sorted(per_year)
    out = []
    for i, y in enumerate(years):
        prev = per_year[years[i - 1]] if i > 0 else None
        current = per_year[y]
        yoy = ((current - prev) / prev) if prev and prev > 0 else None
        out.append({"year": y, "count": current, "yoy": yoy})
    return out


def apply_topic_filter(records: list[dict[str, Any]], topic: TopicDefinition | None, ad_hoc_query: str | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not topic and not ad_hoc_query:
        return records, {"mode": "none", "matched": len(records)}

    matched: list[dict[str, Any]] = []
    scores: list[float] = []
    if topic:
        matcher = TopicMatcher(topic)
        for item in records:
            score = matcher.score_text(record_text(item))
            if score.matched:
                matched.append(item)
                scores.append(score.score)
        return matched, {"mode": "topic", "matched": len(matched), "avg_score": (sum(scores) / len(scores) if scores else 0.0)}

    for item in records:
        score = ad_hoc_match_score(record_text(item), ad_hoc_query or "")
        if score.matched:
            matched.append(item)
            scores.append(score.score)
    return matched, {"mode": "ad_hoc", "matched": len(matched), "avg_score": (sum(scores) / len(scores) if scores else 0.0)}


def topic_overview(records: list[dict[str, Any]], settings: AppSettings | None) -> dict[str, Any]:
    by_year: dict[int, int] = defaultdict(int)
    by_publisher: Counter[str] = Counter()
    by_journal: Counter[str] = Counter()
    pub_years: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    journal_years: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))

    for item in records:
        pub_date = get_published_date(item)
        if not pub_date:
            continue
        year = pub_date.year
        publisher = (item.get("publisher") or "Unknown").strip() or "Unknown"
        journal = (item.get("container-title") or ["Unknown"])[0] or "Unknown"
        by_year[year] += 1
        by_publisher[publisher] += 1
        by_journal[journal] += 1
        pub_years[publisher][year] += 1
        journal_years[journal][year] += 1

    series = _yoy_series(dict(by_year))
    years = sorted(by_year)
    cagr = _cagr(by_year[years[0]], by_year[years[-1]], len(years) - 1) if len(years) > 1 else None

    top_publishers = []
    for name, count in by_publisher.most_common(10):
        year_map = dict(pub_years[name])
        y = sorted(year_map)
        growth = _cagr(year_map[y[0]], year_map[y[-1]], len(y) - 1) if len(y) > 1 else None
        top_publishers.append({"name": name, "count": count, "cagr": growth, "per_year": year_map})

    top_journals = []
    for name, count in by_journal.most_common(10):
        top_journals.append({"name": name, "count": count, "publisher": "n/a", "per_year": dict(journal_years[name])})

    return {"per_year": dict(sorted(by_year.items())), "yearly_growth": series, "cagr": cagr, "top_publishers": top_publishers, "top_journals": top_journals}


def compare_publishers(records: list[dict[str, Any]], selected_publishers: list[str], settings: AppSettings) -> dict[str, Any]:
    publisher_set = {p.lower() for p in selected_publishers}
    by_pub_year: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))

    for item in records:
        pub_name = (item.get("publisher") or "Unknown").strip()
        pub_l = pub_name.lower()
        if publisher_set and all(alias not in pub_l for alias in publisher_set):
            continue
        pub_date = get_published_date(item)
        if not pub_date:
            continue
        by_pub_year[pub_name][pub_date.year] += 1

    all_years = sorted({y for years in by_pub_year.values() for y in years})
    shares: dict[str, dict[int, float]] = defaultdict(dict)
    for year in all_years:
        total = sum(years.get(year, 0) for years in by_pub_year.values())
        if total == 0:
            continue
        for pub, years in by_pub_year.items():
            shares[pub][year] = years.get(year, 0) / total

    growth = {}
    for pub, year_map in by_pub_year.items():
        y = sorted(year_map)
        growth[pub] = _cagr(year_map[y[0]], year_map[y[-1]], len(y) - 1) if len(y) > 1 else None

    return {"per_publisher_per_year": {k: dict(v) for k, v in by_pub_year.items()}, "market_share": {k: dict(v) for k, v in shares.items()}, "growth": growth}


def institutions_breakdown(records: list[dict[str, Any]]) -> dict[str, Any]:
    counter: Counter[str] = Counter()
    canonical: dict[str, str] = {}
    countries: Counter[str] = Counter()
    for item in records:
        for author in item.get("author") or []:
            for affiliation in author.get("affiliation") or []:
                name = affiliation.get("name")
                if not name:
                    continue
                key = _norm_inst(name)
                if not key:
                    continue
                canonical.setdefault(key, name.strip())
                counter[key] += 1
                country = _extract_country(name)
                if country:
                    countries[country] += 1

    top = [{"institution": canonical[k], "count": v} for k, v in counter.most_common(20)]
    country_rollups = [{"country": c, "count": n} for c, n in countries.most_common(20)]
    return {"top_institutions": top, "country_rollups": country_rollups}


def journal_intelligence(records: list[dict[str, Any]], top_n: int = 15) -> dict[str, Any]:
    by_journal: Counter[str] = Counter()
    details: dict[str, dict[str, Any]] = defaultdict(lambda: {"publisher": "Unknown", "per_year": defaultdict(int)})
    for item in records:
        journal = (item.get("container-title") or ["Unknown"])[0] or "Unknown"
        pub = (item.get("publisher") or "Unknown").strip() or "Unknown"
        year_date = get_published_date(item)
        by_journal[journal] += 1
        details[journal]["publisher"] = pub
        if year_date:
            details[journal]["per_year"][year_date.year] += 1

    result = []
    for journal, count in by_journal.most_common(top_n):
        series = dict(sorted(details[journal]["per_year"].items()))
        result.append({"journal": journal, "publisher": details[journal]["publisher"], "count": count, "per_year": series})
    return {"top_journals": result}


def time_to_pub(records: list[dict[str, Any]]) -> dict[str, Any]:
    c2p_values: list[int] = []
    a2p_values: list[int] = []
    c2p_year: dict[int, list[int]] = defaultdict(list)
    a2p_year: dict[int, list[int]] = defaultdict(list)

    for item in records:
        published = get_published_date(item)
        if not published:
            continue
        created = get_created_date(item)
        accepted = get_accepted_date(item)
        if created:
            lag = (published - created).days
            if 0 <= lag <= 5000:
                c2p_values.append(lag)
                c2p_year[published.year].append(lag)
        if accepted:
            lag = (published - accepted).days
            if 0 <= lag <= 5000:
                a2p_values.append(lag)
                a2p_year[published.year].append(lag)

    def avg(values: list[int]) -> float | None:
        return (sum(values) / len(values)) if values else None

    return {
        "metrics": {"created_to_published_days": avg(c2p_values), "accepted_to_published_days": avg(a2p_values)},
        "coverage": {
            "created_to_published_rate": len(c2p_values) / len(records) if records else 0.0,
            "accepted_to_published_rate": len(a2p_values) / len(records) if records else 0.0,
        },
        "trend": {
            "created_to_published": {year: avg(values) for year, values in sorted(c2p_year.items())},
            "accepted_to_published": {year: avg(values) for year, values in sorted(a2p_year.items())},
        },
    }


def emerging_topics(records_by_topic: dict[str, list[dict[str, Any]]], topic_defs: list[TopicDefinition], lookback_years: int) -> dict[str, Any]:
    topic_index = {t.key: t for t in topic_defs}
    ranking = []
    for key, records in records_by_topic.items():
        trend = topic_overview(records, settings=None)
        per_year = trend["per_year"]
        if not per_year:
            continue
        years = sorted(per_year)
        cutoff = years[-1] - lookback_years + 1
        recent = {y: c for y, c in per_year.items() if y >= cutoff}
        if len(recent) < 2:
            continue
        ryears = sorted(recent)
        growth = _cagr(recent[ryears[0]], recent[ryears[-1]], len(ryears) - 1)
        sparkline = [recent[y] for y in ryears]
        ranking.append({
            "topic_key": key,
            "topic_name": topic_index.get(key).name if key in topic_index else key,
            "total_volume": sum(per_year.values()),
            "growth_rate": growth,
            "sparkline": sparkline,
        })

    ranking.sort(key=lambda x: ((x["growth_rate"] or -999), x["total_volume"]), reverse=True)
    return {"ranked_topics": ranking}


def gap_analysis(records_by_topic: dict[str, list[dict[str, Any]]], target_publisher: str, settings: AppSettings, topic_defs: list[TopicDefinition]) -> dict[str, Any]:
    topic_index = {t.key: t for t in topic_defs}
    opportunities = []
    target_l = target_publisher.lower()
    for key, records in records_by_topic.items():
        trend = topic_overview(records, settings=settings)
        per_year = trend["per_year"]
        if not per_year or sum(per_year.values()) < settings.gap_min_topic_volume:
            continue

        years = sorted(per_year)
        overall_growth = _cagr(per_year[years[0]], per_year[years[-1]], len(years) - 1) if len(years) > 1 else None
        if overall_growth is None or overall_growth < settings.gap_min_topic_cagr:
            continue

        total = len(records)
        target_count = sum(1 for r in records if target_l in (r.get("publisher") or "").lower())
        target_share = target_count / total if total else 0.0
        if target_share > settings.gap_max_target_share:
            continue

        score = overall_growth * (1.0 - target_share) * math.log(total + 1)
        opportunities.append({
            "topic_key": key,
            "topic_name": topic_index.get(key).name if key in topic_index else key,
            "overall_growth": overall_growth,
            "target_share": target_share,
            "topic_volume": total,
            "opportunity_score": score,
            "explanation": f"High growth ({overall_growth:.1%}) with low {target_publisher} share ({target_share:.1%}).",
        })

    opportunities.sort(key=lambda x: x["opportunity_score"], reverse=True)
    return {"target_publisher": target_publisher, "opportunities": opportunities}
