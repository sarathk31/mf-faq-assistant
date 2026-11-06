"""Rule-based question classifier.

Order matters. Safety checks (PII, prompt-injection, advice, performance) run
before any factual routing, so a scheme name inside an advice question can never
turn it into a factual query.
"""
import re
from dataclasses import dataclass, field

from rag.schemes import detect_plan, detect_schemes, mentions_other_fund

FACTUAL_SCHEME_QUERY = "FACTUAL_SCHEME_QUERY"
GENERAL_INVESTOR_SERVICE_QUERY = "GENERAL_INVESTOR_SERVICE_QUERY"
EDUCATIONAL_QUERY = "EDUCATIONAL_QUERY"
PERFORMANCE_QUERY = "PERFORMANCE_QUERY"
INVESTMENT_ADVICE_QUERY = "INVESTMENT_ADVICE_QUERY"
OUT_OF_SCOPE_QUERY = "OUT_OF_SCOPE_QUERY"
AMBIGUOUS_QUERY = "AMBIGUOUS_QUERY"
PII_CONTAINING_QUERY = "PII_CONTAINING_QUERY"
SECURITY_QUERY = "OUT_OF_SCOPE_QUERY"  # prompt-reveal / injection attempts are refused as out of scope

# ---------- PII ----------
PII_PATTERNS = {
    "PAN": r"\b[A-Za-z]{5}\d{4}[A-Za-z]\b",
    "Aadhaar": r"\b\d{4}\s?\d{4}\s?\d{4}\b",
    "email": r"[\w.+-]+@[\w-]+\.[\w.-]+",
    "phone": r"(?<!\d)(?:\+91[\s-]?)?[6-9]\d{9}(?!\d)",
    "OTP": r"\b(?:otp|one[\s-]?time password)\b\D{0,15}\d{4,8}\b",
    "account number": r"\b(?:a/?c|account|acct|folio)\s*(?:no\.?|number|#)?\s*[:\-]?\s*\d{6,18}\b",
    "long number": r"(?<!\d)\d{9,18}(?!\d)",
}
PERSONAL_ACCOUNT_REQUEST = re.compile(
    r"\b(my|mine)\b.{0,40}\b(folio|portfolio|holding|holdings|balance|units|account|statement status|transactions?|investments?|sip status)\b"
    r"|\b(check|show|fetch|retrieve|look ?up|tell me)\b.{0,30}\b(my)\b",
    re.I,
)

# ---------- Prompt injection / system reveal ----------
SECURITY = re.compile(
    r"(system prompt|your prompt|your instructions|ignore (all |the )?(previous|above|prior)|developer mode|jailbreak|"
    r"api key|apikey|secret key|environment variable|\.env\b|reveal (your|the) (rules|prompt|config)|act as|pretend (to be|you are))",
    re.I,
)

# ---------- Advice ----------
ADVICE = re.compile(
    r"\b(should i|shall i|should we|do you recommend|would you recommend|recommend(ed|ation)?|suggest|advise|"
    r"which (fund|scheme|one) (is|should|would|to)|best (fund|scheme|option|choice|for)|better (than|option|fund|scheme|choice)|"
    r"is it (a )?(good|worth|safe|wise|right)|worth (it|investing|buying)|good (time|idea|investment|fund|choice)|"
    r"right (fund|scheme|time)|suitable for me|for me\b|my (age|salary|income|goal|risk appetite|risk profile)|"
    r"stop my sip|pause my sip|exit now|redeem now|allocate|allocation|how much (should|to) invest|"
    r"where (should|to) invest|switch (from|to|my)|move my|buy or sell|hold or sell|safe|guaranteed?|risk[- ]free|good reason|reason to (buy|invest|sell)|(buy|sell|invest in) (it|this|now|more))\b",
    re.I,
)
COMPARE = re.compile(r"\b(vs\.?|versus|compare|comparison|or)\b", re.I)

# ---------- Performance ----------
PERFORMANCE = re.compile(
    r"\b(return|returns|cagr|performance|performed|perform|grow|growth rate|gain(ed)?|yield|outperform|"
    r"nav (will|forecast|prediction|tomorrow|next)|predict|forecast|future value|how much will i (get|make|earn)|"
    r"highest return|beat the market|profit|go (up|down)|rise|fall|crash|next (week|month|year)|will .{0,25}(increase|decrease|grow|drop))\b",
    re.I,
)

# ---------- Topics ----------
TOPICS = {
    "expense_ratio": r"expense ratio|\bter\b|total expense|annual (fee|charge)|fund (fee|charges?)|management fee",
    "exit_load": r"exit load|exit charge|redemption (charge|fee|load)|early (withdrawal|redemption)|withdrawal charge|withdraw\w* .{0,25}early|early .{0,15}withdraw|charge (if|for|on|when) (i )?(withdraw|redeem|sell|exit)|penalty (for|on|if) (withdraw|redeem|exit)",
    "min_sip": r"\bsip\b|systematic investment",
    "min_lumpsum": r"lump ?sum|one[- ]time|minimum (investment|application|purchase|amount)|additional purchase|initial investment",
    "lock_in": r"lock[- ]?in|locked|lock period",
    "riskometer": r"risk[- ]?o[- ]?meter|riskometer|risk level|how risky|risk category|risk grade",
    "benchmark": r"benchmark|index (it )?(tracks|follows)|compared (to|against|with)",
    "plans_options": r"\bplans?\b|\boptions?\b|\bidcw\b|dividend|growth option|direct or regular|payout|reinvest",
    "documents": r"\bsid\b|\bkim\b|scheme information document|key information memorandum|scheme documents?|offer document",
    "factsheet": r"fact ?sheet|fund facts",
    "account_statement": r"account statement|\bsoa\b|statement of account|download (my )?statement|transaction history|get (a |my )?statement|\bstatements?\b",
    "capital_gains": r"capital[- ]?gains?|tax statement|realised gains|realized gains|\bitr\b",
    "cas": r"\bcas\b|consolidated account statement",
    "overview": r"what (kind|type|category) of (fund|scheme)|which category|fund category|scheme category|what is hdfc|formerly|former name|earlier name|previous name|renamed|old name|name change",
    "nav": r"\bnav\b|net asset value",
    "aum": r"\baum\b|assets under management|fund size|corpus size",
    "holdings": r"holdings?|top stocks|portfolio (of|stocks)|which stocks|sector allocation",
    "fund_manager": r"fund manager|who manages",
}
SCHEME_SPECIFIC_TOPICS = {"expense_ratio", "exit_load", "min_sip", "min_lumpsum", "lock_in", "riskometer",
                          "benchmark", "plans_options", "overview", "nav", "aum", "holdings", "fund_manager"}
SERVICE_TOPICS = {"account_statement", "capital_gains", "cas"}
PRONOUN = re.compile(r"\b(its|it's|this (fund|scheme)|that (fund|scheme)|the (fund|scheme)|this one|same (fund|scheme))\b", re.I)
DEFINITION = re.compile(r"^\s*(what (is|are|does|do)|define|meaning of|explain|what's|whats)\b", re.I)


@dataclass
class Classification:
    category: str
    topics: list = field(default_factory=list)
    schemes: list = field(default_factory=list)
    plan: str | None = None
    pii_types: list = field(default_factory=list)
    reason: str = ""


def find_pii(text: str) -> list[str]:
    found = []
    for label, pat in PII_PATTERNS.items():
        if re.search(pat, text, re.I):
            found.append(label)
    if "long number" in found and len(found) > 1:
        found.remove("long number")
    return found


def detect_topics(text: str) -> list[str]:
    return [name for name, pat in TOPICS.items() if re.search(pat, text, re.I)]


def classify(question: str, context_scheme: str | None = None) -> Classification:
    q = question.strip()
    schemes = detect_schemes(q)
    topics = detect_topics(q)
    plan = detect_plan(q)

    pii = find_pii(q)
    if pii:
        return Classification(PII_CONTAINING_QUERY, topics, schemes, plan, pii, "personal identifier detected")
    if PERSONAL_ACCOUNT_REQUEST.search(q) and not DEFINITION.search(q) and not re.search(r"\bhow\b", q, re.I):
        return Classification(PII_CONTAINING_QUERY, topics, schemes, plan, [], "asks for personal account data")
    if SECURITY.search(q):
        return Classification(SECURITY_QUERY, topics, schemes, plan, [], "prompt or configuration request")

    is_advice = bool(ADVICE.search(q)) or (len(schemes) >= 2 and bool(COMPARE.search(q)) and not topics)
    if is_advice:
        # "should I" + "how do I download statement" style service questions are still service questions.
        if topics and set(topics) <= SERVICE_TOPICS and re.search(r"\bhow\b", q, re.I):
            return Classification(GENERAL_INVESTOR_SERVICE_QUERY, topics, schemes, plan, [], "service how-to")
        if PERFORMANCE.search(q):
            return Classification(INVESTMENT_ADVICE_QUERY, topics, schemes, plan, [], "advice with return expectation")
        return Classification(INVESTMENT_ADVICE_QUERY, topics, schemes, plan, [], "recommendation or suitability request")
    if PERFORMANCE.search(q) and not set(topics) & {"expense_ratio", "exit_load", "benchmark", "min_sip", "min_lumpsum"}:
        return Classification(PERFORMANCE_QUERY, topics, schemes, plan, [], "returns / performance request")

    if mentions_other_fund(q):
        return Classification(OUT_OF_SCOPE_QUERY, topics, schemes, plan, [], "scheme outside the corpus")

    if not schemes and context_scheme and topics and set(topics) & SCHEME_SPECIFIC_TOPICS:
        schemes = [context_scheme]

    # "its expense ratio", "this fund's exit load": a scheme is implied but not named.
    if not schemes and PRONOUN.search(q) and set(topics) & SCHEME_SPECIFIC_TOPICS:
        return Classification(AMBIGUOUS_QUERY, topics, schemes, plan, [], "scheme implied but not named")

    if topics and set(topics) <= SERVICE_TOPICS | {"documents", "factsheet"} and not schemes:
        return Classification(GENERAL_INVESTOR_SERVICE_QUERY, topics, schemes, plan, [], "investor service")
    if set(topics) & SERVICE_TOPICS:
        return Classification(GENERAL_INVESTOR_SERVICE_QUERY, topics, schemes, plan, [], "investor service")

    if not schemes and not re.search(r"\bmean|meaning|define|explain\b", q, re.I) and re.search(
            r"\bthe (expense ratio|ter|exit load|lock[- ]?in|riskometer|risk-o-meter|benchmark|minimum sip|sip)\b", q, re.I):
        return Classification(AMBIGUOUS_QUERY, topics, schemes, plan, [], "scheme-specific fact without a scheme")
    if DEFINITION.search(q) and not schemes and re.search(r"\b(a|an|the)?\s*(expense ratio|ter|exit load|lock[- ]?in|riskometer|risk-o-meter|benchmark)\b", q, re.I):
        return Classification(EDUCATIONAL_QUERY, topics, schemes, plan, [], "definition")

    if schemes and topics:
        return Classification(FACTUAL_SCHEME_QUERY, topics, schemes, plan, [], "scheme fact")
    if schemes and not topics:
        return Classification(AMBIGUOUS_QUERY, topics, schemes, plan, [], "scheme named but no fact requested")
    if topics and set(topics) & SCHEME_SPECIFIC_TOPICS:
        return Classification(AMBIGUOUS_QUERY, topics, schemes, plan, [], "scheme-specific fact without a scheme")
    if topics:
        return Classification(GENERAL_INVESTOR_SERVICE_QUERY, topics, schemes, plan, [], "general documents")
    return Classification(OUT_OF_SCOPE_QUERY, topics, schemes, plan, [], "no supported topic")
