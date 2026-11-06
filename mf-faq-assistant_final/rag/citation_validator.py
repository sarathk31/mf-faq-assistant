"""Post-generation checks: one official link, grounded numbers, length, no advice."""
import re

from rag.retriever import load_chunks

ADVICE_LEAK = re.compile(r"\b(you should|we recommend|i recommend|consider investing|good (choice|option|investment)|"
                         r"better option|suitable for you|you may want to (invest|buy|sell|switch))\b", re.I)
URL = re.compile(r"https?://\S+|www\.\S+", re.I)
NUM = re.compile(r"\d+(?:[.,]\d+)*")


def allowed_urls() -> set[str]:
    return {c["source_url"] for c in load_chunks()}


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z(])", text.strip())
    return [p for p in parts if p]


def _numbers(text: str) -> set[str]:
    return {n.replace(",", "") for n in NUM.findall(text)}


def validate_answer(answer: str, evidence: list[dict], question: str = "") -> tuple[bool, str]:
    """Return (ok, reason). The LLM answer must not add numbers or advice, and must stay short."""
    if not answer or answer.strip().upper().startswith("NOT_FOUND"):
        return False, "model reported not found"
    if URL.search(answer):
        return False, "answer contains a URL"
    if ADVICE_LEAK.search(answer):
        return False, "advice language"
    if len(split_sentences(answer)) > 3:
        return False, "more than three sentences"
    allowed = _numbers(" ".join(c["text"] + " " + c.get("quote", "") for c in evidence) + " " + question)
    extra = {n for n in _numbers(answer) if n not in allowed and n.lstrip("0") not in {a.lstrip("0") for a in allowed}}
    if extra:
        return False, f"ungrounded numbers {sorted(extra)}"
    return True, "ok"


def validate_citation(url: str | None) -> bool:
    return url is None or url in allowed_urls()


def trim_to_sentences(text: str, n: int = 3) -> str:
    return " ".join(split_sentences(text)[:n])
