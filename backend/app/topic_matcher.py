from __future__ import annotations

import re
from dataclasses import dataclass

from .models import TopicDefinition

_WORD = re.compile(r"\w+")


@dataclass
class MatchResult:
    matched: bool
    score: float
    positive_hits: int
    negative_hits: int


class TopicMatcher:
    def __init__(self, topic: TopicDefinition):
        self.topic = topic
        self.positives = [s.lower() for s in (topic.keywords + topic.synonyms)]
        self.negatives = [s.lower() for s in topic.negative_keywords]

    @staticmethod
    def _contains_phrase(text: str, phrase: str) -> bool:
        return phrase in text

    def score_text(self, text: str) -> MatchResult:
        text_l = text.lower()
        pos_hits = sum(1 for term in self.positives if self._contains_phrase(text_l, term))
        neg_hits = sum(1 for term in self.negatives if self._contains_phrase(text_l, term))
        score = (2.0 * pos_hits) - (2.5 * neg_hits)
        return MatchResult(matched=pos_hits > 0 and score > 0, score=score, positive_hits=pos_hits, negative_hits=neg_hits)


def ad_hoc_terms(query: str) -> list[str]:
    terms = [t.lower() for t in _WORD.findall(query or "") if len(t) > 2]
    return sorted(set(terms))


def ad_hoc_match_score(text: str, query: str) -> MatchResult:
    terms = ad_hoc_terms(query)
    text_l = text.lower()
    pos_hits = sum(1 for t in terms if t in text_l)
    score = float(pos_hits)
    return MatchResult(matched=pos_hits > 0, score=score, positive_hits=pos_hits, negative_hits=0)
