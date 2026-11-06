import pytest

from rag.retriever import load_chunks, retrieve

FACTS = [
    ("HDFC Flexi Cap Fund expense ratio", "HDFC Flexi Cap Fund", "expense_ratio"),
    ("HDFC Liquid Fund exit load", "HDFC Liquid Fund", "exit_load"),
    ("HDFC ELSS lock in", "HDFC ELSS - Tax Saver Fund", "lock_in"),
    ("HDFC Large Cap benchmark", "HDFC Large Cap Fund", "benchmark"),
    ("HDFC Liquid riskometer", "HDFC Liquid Fund", "riskometer"),
    ("minimum sip HDFC ELSS", "HDFC ELSS - Tax Saver Fund", "min_sip"),
]


@pytest.mark.parametrize("q,scheme,topic", FACTS)
def test_top_hit_is_right_scheme_and_topic(q, scheme, topic):
    hits = retrieve(q, schemes=[scheme], topics=[topic], only_topics={topic})
    assert hits and hits[0]["scheme_name"] == scheme and hits[0]["topic"] == topic


def test_scheme_filter_never_leaks_other_schemes():
    for h in retrieve("exit load expense ratio benchmark", schemes=["HDFC Liquid Fund"], top_k=50):
        assert h["scheme_name"] == "HDFC Liquid Fund"


def test_every_chunk_has_required_metadata():
    keys = {"source_id", "source_title", "source_url", "organization", "scheme_name", "scheme_category", "document_type",
            "topic", "publication_date", "accessed_date", "last_verified_date", "applicable_plan", "applicable_option", "text", "quote"}
    for c in load_chunks():
        assert keys <= set(c), c["chunk_id"]
        assert c["source_url"].startswith(("https://www.hdfcfund.com/", "https://files.hdfcfund.com/", "https://www.sebi.gov.in/"))
