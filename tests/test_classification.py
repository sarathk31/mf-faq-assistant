import json
from pathlib import Path

import pytest

from rag.classifier import classify

CASES = json.loads((Path(__file__).resolve().parent.parent / "evaluation" / "sample_questions.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_category(case):
    assert classify(case["question"]).category == case["category"]


@pytest.mark.parametrize("q", [
    "Should I invest in HDFC ELSS for its 3 year lock-in?",
    "Is the exit load of HDFC Flexi Cap a good reason to buy it?",
    "Recommend the best HDFC fund with low expense ratio",
])
def test_scheme_name_does_not_turn_advice_into_fact(q):
    assert classify(q).category == "INVESTMENT_ADVICE_QUERY"


def test_context_scheme_resolves_follow_up():
    c = classify("What is the exit load?", context_scheme="HDFC Liquid Fund")
    assert c.category == "FACTUAL_SCHEME_QUERY" and c.schemes == ["HDFC Liquid Fund"]
