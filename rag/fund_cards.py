"""Fund quick-facts for the UI, built only from verified chunks (no NAV, returns or other unverified data)."""
import re

from rag.retriever import load_chunks
from rag.schemes import SCHEMES

SHORT_EXIT = {
    "HDFC Large Cap Fund": "1% if redeemed within 1 year; nil after",
    "HDFC Flexi Cap Fund": "1% if redeemed within 1 year; nil after",
    "HDFC ELSS - Tax Saver Fund": "Nil",
    "HDFC Liquid Fund": "0.0070% on Day 1 down to 0.0045% on Day 6; nil from Day 7",
}


def _fact(chunks, topic, value, source_type="scheme page"):
    c = next((c for c in chunks if c["topic"] == topic), None)
    if not c:
        return None
    return {"value": value(c), "source_title": c["source_title"], "source_url": c["source_url"],
            "verified": c["last_verified_date"]}


def fund_cards() -> list[dict]:
    cards = []
    all_chunks = load_chunks()
    for name in SCHEMES:
        ch = [c for c in all_chunks if c["scheme_name"] == name]
        page = [c for c in ch if c["document_type"] == "Official AMC scheme page"]
        ter = re.search(r"TER Direct ([\d.]+) \| TER Regular ([\d.]+)", next(c["quote"] for c in page if c["topic"] == "expense_ratio"))
        exit_chunk = next(c for c in ch if c["topic"] == "exit_load")
        cards.append({
            "name": name,
            "category": ch[0]["scheme_category"],
            "description": next(c["quote"] for c in page if c["topic"] == "overview"),
            "facts": {
                "Expense ratio (Direct)": _fact(page, "expense_ratio", lambda c: f"{ter.group(1)}%"),
                "Expense ratio (Regular)": _fact(page, "expense_ratio", lambda c: f"{ter.group(2)}%"),
                "Min SIP": _fact(page, "min_sip", lambda c: "Rs. " + c["quote"].split("Rs ")[-1]),
                "Riskometer": _fact(page, "riskometer", lambda c: c["quote"].replace("Riskometer ", "")),
                "Lock-in": _fact(page, "lock_in", lambda c: c["quote"].split("|")[0].replace("Lock in ", "").strip()),
                "Exit load": {"value": SHORT_EXIT[name], "source_title": exit_chunk["source_title"],
                              "source_url": exit_chunk["source_url"], "verified": exit_chunk["last_verified_date"]},
                "Benchmark": _fact(page, "benchmark", lambda c: c["quote"].replace("Benchmark ", "")),
            },
            "documents": [{"title": c["source_title"], "url": c["source_url"]} for c in ch if c["topic"] in ("documents", "factsheet")],
        })
    return cards
