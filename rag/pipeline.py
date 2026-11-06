"""End-to-end answer pipeline:
validate input -> classify -> scope/safety decision -> retrieve -> evidence check -> generate -> citation check.
Nothing the user types is stored or logged.
"""
from datetime import date

from config.settings import MAX_QUESTION_CHARS, MIN_RETRIEVAL_SCORE
from rag import classifier as C
from rag.answer_generator import generate
from rag.citation_validator import validate_citation
from rag.retriever import load_chunks, retrieve
from rag.schemes import SCHEME_PAGES, SCHEMES

COVERED = ", ".join(SCHEMES)
UNSUPPORTED_TOPICS = {"nav", "aum", "holdings", "fund_manager"}
KIM_URL = {c["scheme_name"]: c["source_url"] for c in load_chunks() if c["topic"] == "plans_options"}
FACTS_URL = {c["scheme_name"]: (c["source_title"], c["source_url"]) for c in load_chunks()
             if c["topic"] == "factsheet" and c["scheme_name"] != "General"}


def _src(source_id: str) -> dict:
    c = next(c for c in load_chunks() if c["source_id"] == source_id)
    return {"title": c["source_title"], "url": c["source_url"], "verified": c["last_verified_date"]}


def _fmt(iso: str) -> str:
    try:
        return date.fromisoformat(iso).strftime("%d %b %Y").lstrip("0")
    except ValueError:
        return iso


def _response(status, category, answer, source=None):
    if source and not validate_citation(source["url"]):
        source = None  # never show a link that is not in the verified corpus
    return {
        "status": status,              # factual | clarification | refusal | not_found
        "category": category,
        "answer": answer,
        "source_title": source["title"] if source else None,
        "source_url": source["url"] if source else None,
        "last_updated": f"Last updated from sources: {_fmt(source['verified'])}" if source else None,
    }


def answer_question(question: str, context_scheme: str | None = None) -> dict:
    resp = _answer(question, context_scheme)
    if "scheme" not in resp:
        found = C.detect_schemes(question or "")
        resp["scheme"] = found[0] if len(found) == 1 else None  # lets the UI resolve follow-ups like "its exit load"
    return resp


def _answer(question: str, context_scheme: str | None = None) -> dict:
    q = (question or "").strip()
    if not q:
        return _response("clarification", "INVALID_INPUT", "Please type a question about one of the covered HDFC Mutual Fund schemes.")
    if len(q) > MAX_QUESTION_CHARS:
        return _response("clarification", "INVALID_INPUT", f"Please keep your question under {MAX_QUESTION_CHARS} characters.")

    cls = C.classify(q, context_scheme)
    cat = cls.category
    scheme = cls.schemes[0] if len(cls.schemes) == 1 else None

    if cat == C.PII_CONTAINING_QUERY:
        msg = ("I can't process personal or account information, so please don't share PAN, Aadhaar, folio or account numbers, "
               "OTPs or contact details here. For your own statements or account details, use HDFC Mutual Fund's official service channels.")
        return _response("refusal", cat, msg, _src("S19"))

    if cat == C.INVESTMENT_ADVICE_QUERY:
        msg = ("I can help with factual scheme information, but I can't recommend whether you should buy, sell, switch or stop "
               "a mutual fund investment. You can review the scheme's official documents to understand its features and risks.")
        src = ({"title": f"KIM - {scheme}", "url": KIM_URL[scheme], "verified": "2026-11-04"} if scheme in KIM_URL else _src("S17"))
        return _response("refusal", cat, msg, src)

    if cat == C.PERFORMANCE_QUERY:
        msg = ("I don't share, compare or predict returns. Past performance and NAV history are published in HDFC Mutual Fund's "
               "official factsheet.")
        if scheme in FACTS_URL:
            title, url = FACTS_URL[scheme]
            return _response("refusal", cat, msg, {"title": title, "url": url, "verified": "2026-11-04"})
        return _response("refusal", cat, msg, _src("S15"))

    if cat == C.OUT_OF_SCOPE_QUERY:
        if cls.reason == "prompt or configuration request":
            return _response("refusal", cat, "I can't share my internal instructions or configuration. I can answer factual "
                             f"questions about {COVERED}.")
        if cls.reason == "scheme outside the corpus":
            return _response("not_found", cat, "That scheme isn't in my verified source collection. I only cover "
                             f"{COVERED}.", _src("S17"))
        return _response("not_found", cat, "I can only answer factual questions about the covered HDFC Mutual Fund schemes "
                         "and their investor services, such as expense ratio, exit load, minimum SIP, lock-in, riskometer, "
                         "benchmark and statements.")

    if cat == C.AMBIGUOUS_QUERY:
        if cls.schemes and not cls.topics:
            return _response("clarification", cat, f"What would you like to know about {cls.schemes[0]}? I can answer questions "
                             "on its expense ratio, exit load, minimum SIP, lock-in, riskometer, benchmark, plans or documents.")
        return _response("clarification", cat, f"Which scheme do you mean? I cover {COVERED}.")

    if cat == C.FACTUAL_SCHEME_QUERY and len(cls.schemes) > 1:
        return _response("clarification", cat, "Please ask about one scheme at a time so I can cite the right official source. "
                         f"I cover {COVERED}.")

    if cat == C.FACTUAL_SCHEME_QUERY and set(cls.topics) <= UNSUPPORTED_TOPICS:
        return _response("not_found", cat, "I couldn't verify that detail from the official sources currently available in my "
                         f"knowledge base. You can check {scheme}'s official scheme page.",
                         {"title": f"{scheme} - official scheme page", "url": SCHEME_PAGES[scheme], "verified": "2026-11-04"})

    # ---- Retrieval ----
    if cat == C.FACTUAL_SCHEME_QUERY:
        topics = [t for t in cls.topics if t not in UNSUPPORTED_TOPICS]
        hits = retrieve(q, schemes=[scheme], topics=topics, only_topics=set(topics))  # evidence must match the requested fact
    elif cat == C.EDUCATIONAL_QUERY:
        defs = {c["topic"] for c in load_chunks() if c["topic"].startswith("definition_")}
        wanted = {f"definition_{t}" for t in cls.topics} & defs
        hits = retrieve(q, topics=cls.topics, only_topics=wanted or defs)
    else:  # GENERAL_INVESTOR_SERVICE_QUERY
        hits = retrieve(q, schemes=[scheme] if scheme else None, general_only=not scheme, topics=cls.topics)
        if cls.topics:
            hits = [h for h in hits if h["topic"] in cls.topics] or hits

    if not hits or hits[0]["score"] < MIN_RETRIEVAL_SCORE:
        return _response("not_found", cat, "I couldn't verify that detail from the official sources currently available in my "
                         "knowledge base.", _src("S17"))

    top = hits[0]
    evidence = [h for h in hits if h["source_id"] == top["source_id"]][:2]  # one source -> one citation
    answer, mode = generate(q, evidence, cls.plan)
    if answer == "NOT_FOUND":
        return _response("not_found", cat, "I couldn't verify that detail from the official sources currently available in my "
                         "knowledge base.", {"title": top["source_title"], "url": top["source_url"], "verified": top["last_verified_date"]})
    resp = _response("factual", cat, answer,
                     {"title": top["source_title"], "url": top["source_url"], "verified": top["last_verified_date"]})
    resp["mode"] = mode
    resp["scheme"] = top["scheme_name"]
    return resp
