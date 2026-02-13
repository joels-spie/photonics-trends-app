from app.crossref import build_filter_string


def test_build_filter_string_contains_required_fields():
    value = build_filter_string(
        from_pub_date="2020-01-01",
        until_pub_date="2024-12-31",
        doc_types=["journal-article", "proceedings-article"],
        publisher_names=["SPIE"],
        prefixes=["10.1117"],
        container_titles=["Optics Express"],
    )
    assert "from-pub-date:2020-01-01" in value
    assert "until-pub-date:2024-12-31" in value
    assert "type:journal-article" in value
    assert "prefix:10.1117" in value
    assert "container-title:Optics Express" in value
    assert "publisher-name" not in value
