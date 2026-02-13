from app.topic_matcher import TopicMatcher
from app.models import TopicDefinition


def test_topic_matcher_positive_hit():
    topic = TopicDefinition(
        key="silicon_photonics",
        name="Silicon Photonics",
        keywords=["silicon photonics"],
        synonyms=["photonic integrated circuit"],
        negative_keywords=["silicon solar"],
    )
    matcher = TopicMatcher(topic)
    result = matcher.score_text("A new silicon photonics platform for PIC transceivers")
    assert result.matched is True
    assert result.score > 0


def test_topic_matcher_negative_penalty():
    topic = TopicDefinition(
        key="silicon_photonics",
        name="Silicon Photonics",
        keywords=["silicon photonics"],
        synonyms=[],
        negative_keywords=["silicon solar"],
    )
    matcher = TopicMatcher(topic)
    result = matcher.score_text("silicon photonics for silicon solar materials")
    assert result.negative_hits == 1
