"""Scheme and plan detection. Deterministic, so it is easy to explain and test."""
import re

SCHEMES = {
    "HDFC Large Cap Fund": ["hdfc large cap", "large cap fund", "large-cap", "largecap", "large cap", "top 100", "top100"],
    "HDFC Flexi Cap Fund": ["hdfc flexi cap", "flexi cap", "flexicap", "flexi-cap", "flexi"],
    "HDFC ELSS - Tax Saver Fund": ["hdfc elss", "elss tax saver", "tax saver", "taxsaver", "tax saving", "elss"],
    "HDFC Liquid Fund": ["hdfc liquid", "liquid fund", "liquid"],
}

SCHEME_PAGES = {
    "HDFC Large Cap Fund": "https://www.hdfcfund.com/explore/mutual-funds/hdfc-large-cap-fund/direct",
    "HDFC Flexi Cap Fund": "https://www.hdfcfund.com/explore/mutual-funds/hdfc-flexi-cap-fund/direct",
    "HDFC ELSS - Tax Saver Fund": "https://www.hdfcfund.com/explore/mutual-funds/hdfc-elss-tax-saver-fund/direct",
    "HDFC Liquid Fund": "https://www.hdfcfund.com/explore/mutual-funds/hdfc-liquid-fund/direct",
}

# Other AMCs and fund names that are clearly outside the corpus.
OTHER_AMCS = ["sbi", "icici", "axis", "kotak", "nippon", "parag parikh", "ppfas", "mirae", "uti", "dsp",
              "aditya birla", "tata", "quant", "motilal", "franklin", "edelweiss", "bandhan", "canara",
              "groww mutual", "groww nifty", "invesco", "hsbc", "baroda", "sundaram", "mahindra", "zerodha"]
OTHER_HDFC_SCHEMES = ["mid cap", "midcap", "small cap", "smallcap", "balanced advantage", "hybrid", "index fund",
                      "nifty 50", "sensex", "gold", "silver", "short term debt", "money market", "overnight",
                      "gilt", "corporate bond", "multi cap", "multi-asset", "focused", "value fund", "etf",
                      "retirement", "children", "arbitrage", "banking", "pharma", "infrastructure", "manufacturing"]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


def detect_schemes(text: str) -> list[str]:
    t = _norm(text)
    found = []
    for name, aliases in SCHEMES.items():
        if any(re.search(r"\b" + re.escape(a) + r"\b", t) for a in aliases):
            found.append(name)
    # "large cap" inside "flexi cap ... across large cap" is not a separate mention when flexi is named.
    if "HDFC Flexi Cap Fund" in found and "HDFC Large Cap Fund" in found and not re.search(r"large cap fund|top 100", t):
        found.remove("HDFC Large Cap Fund")
    return found


def mentions_other_fund(text: str) -> bool:
    t = _norm(text)
    if any(re.search(r"\b" + re.escape(a) + r"\b", t) for a in OTHER_AMCS):
        return True
    if not detect_schemes(text) and any(re.search(r"\b" + re.escape(s) + r"\b", t) for s in OTHER_HDFC_SCHEMES):
        return True
    return False


def detect_plan(text: str) -> str | None:
    t = _norm(text)
    if re.search(r"\bdirect\b", t):
        return "Direct"
    if re.search(r"\bregular\b", t):
        return "Regular"
    return None
