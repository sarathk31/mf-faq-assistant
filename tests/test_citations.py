import csv
import re
from pathlib import Path

import pytest

from rag.citation_validator import split_sentences, validate_answer
from rag.pipeline import answer_question
from rag.retriever import load_chunks

ROOT = Path(__file__).resolve().parent.parent
SOURCE_URLS = {r["source_url"] for r in csv.DictReader(open(ROOT / "data" / "sources.csv", encoding="utf-8"))}


def test_source_list_size_and_officialness():
    rows = list(csv.DictReader(open(ROOT / "data" / "sources.csv", encoding="utf-8")))
    assert 15 <= len(rows) <= 25
    assert len({r["source_url"] for r in rows}) == len(rows)
    for r in rows:
        assert r["organization"] in {"HDFC Asset Management Company Ltd.", "Securities and Exchange Board of India"}


def test_numbers_in_chunk_text_come_from_verbatim_quote():
    """Every number in a chunk's plain-language text must appear in its verified source wording (or the source registry dates)."""
    allowed_dates = {"21", "2025", "2026", "30", "10", "26", "7", "1", "2", "3", "4", "5", "6", "100"}
    for c in load_chunks():
        nums_text = set(re.findall(r"\d+(?:\.\d+)?", c["text"].replace(",", "")))
        nums_quote = set(re.findall(r"\d+(?:\.\d+)?", (c["quote"] + " " + c["source_title"] + " " + c["publication_date"]).replace(",", "")))
        extra = {n for n in nums_text - nums_quote if n not in allowed_dates}
        assert not extra, (c["chunk_id"], extra)


@pytest.mark.parametrize("case_id", ["F1", "F3", "F5", "F6", "F8", "S1", "S2", "S3", "E1", "E3"])
def test_factual_answers_have_exactly_one_official_link_and_footer(cases, case_id):
    case = next(c for c in cases if c["id"] == case_id)
    r = answer_question(case["question"])
    assert r["status"] == "factual"
    assert r["source_url"] in SOURCE_URLS
    assert r["last_updated"].startswith("Last updated from sources: ")
    assert "http" not in r["answer"]
    assert len(split_sentences(r["answer"])) <= 3


def test_validator_rejects_ungrounded_numbers_and_links():
    ev = [{"text": "The minimum SIP amount for HDFC Liquid Fund is Rs. 100.", "quote": "Min SIP Rs 100"}]
    assert validate_answer("The minimum SIP is Rs. 100.", ev)[0]
    assert not validate_answer("The minimum SIP is Rs. 500.", ev)[0]
    assert not validate_answer("See https://example.com for details.", ev)[0]
    assert not validate_answer("One. Two. Three. Four.", ev)[0]
