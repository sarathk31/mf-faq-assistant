"""LLM generation over retrieved evidence, with a grounded extractive fallback."""
import json
import logging
import urllib.error
import urllib.request

from config.settings import GROQ_API_URL, GROQ_MODEL, LLM_TIMEOUT_SECONDS, groq_api_key
from rag.citation_validator import trim_to_sentences, validate_answer
from rag.system_prompt import SYSTEM_PROMPT, build_user_message

log = logging.getLogger(__name__)


class LLMUnavailable(Exception):
    pass


def call_groq(question: str, evidence: list[dict], plan: str | None) -> str:
    key = groq_api_key()
    if not key:
        raise LLMUnavailable("GROQ_API_KEY is not set")
    body = json.dumps({
        "model": GROQ_MODEL,
        "temperature": 0,
        "max_tokens": 220,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_message(question, evidence, plan)},
        ],
    }).encode()
    req = urllib.request.Request(GROQ_API_URL, data=body, method="POST", headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": "mf-faq-assistant/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=LLM_TIMEOUT_SECONDS) as r:
            data = json.loads(r.read().decode())
        return data["choices"][0]["message"]["content"].strip()
    except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as e:
        # Never log the key or the user's question.
        log.warning("LLM call failed: %s", type(e).__name__)
        raise LLMUnavailable(type(e).__name__) from e


def extractive_answer(evidence: list[dict], plan: str | None) -> str:
    """Deterministic answer straight from the top chunk: used when the LLM is unavailable or fails validation."""
    top = evidence[0]
    text = top["text"]
    if top["topic"] == "expense_ratio" and plan:
        # Keep only the requested plan's value; both values are verbatim in the chunk.
        import re
        m = re.search(rf"(\d+(?:\.\d+)?)% for the {plan} Plan", text)
        if m:
            return (f"The {plan} Plan of {top['scheme_name']} has an expense ratio (TER) of {m.group(1)}%, "
                    "as shown on HDFC Mutual Fund's official scheme page. TER can change over time.")
    return trim_to_sentences(text, 3)


def generate(question: str, evidence: list[dict], plan: str | None) -> tuple[str, str]:
    """Return (answer, mode) where mode is 'llm' or 'extractive'."""
    try:
        answer = call_groq(question, evidence, plan)
        ok, reason = validate_answer(answer, evidence, question)
        if ok:
            return answer, "llm"
        log.info("LLM answer rejected: %s", reason)
        if answer.strip().upper().startswith("NOT_FOUND"):
            return "NOT_FOUND", "llm"
    except LLMUnavailable:
        pass
    return extractive_answer(evidence, plan), "extractive"
