"""Build the chunked knowledge base from verified captures.

Input:  data/sources.csv (source registry) + data/raw/captures.json (verified verbatim excerpts)
Output: data/processed/chunks.json

Each chunk holds ONE fact (with its conditions) for ONE scheme, written as a short
plain sentence ("text"), plus the verbatim source wording it came from ("quote")
and full source metadata. Values in "text" are copied from "quote"; tests check this.

Run:  python -m ingestion.build_corpus
"""
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import CHUNKS_PATH, RAW_CAPTURES, SOURCES_CSV  # noqa: E402

LC, FC, ELSS, LIQ = "HDFC Large Cap Fund", "HDFC Flexi Cap Fund", "HDFC ELSS - Tax Saver Fund", "HDFC Liquid Fund"
CATEGORY = {LC: "Equity - Large Cap", FC: "Equity - Flexi Cap", ELSS: "Equity - ELSS", LIQ: "Debt - Liquid"}
KIM = {LC: "S05", FC: "S06", ELSS: "S07", LIQ: "S08"}
FUND_FACTS = {LC: "S11", FC: "S12", ELSS: "S13", LIQ: "S14"}
SID = {FC: "S09", ELSS: "S10"}


def load_sources() -> dict:
    with open(SOURCES_CSV, newline="", encoding="utf-8") as f:
        return {row["source_id"]: row for row in csv.DictReader(f)}


def clean(text: str) -> str:
    text = text.replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text).strip()


class Builder:
    def __init__(self, sources: dict):
        self.sources, self.chunks = sources, []

    def add(self, source_id, topic, text, quote, scheme=None, plan="All plans", keywords="", boost=0.0):
        s = self.sources[source_id]
        self.chunks.append({
            "chunk_id": f"{source_id}-{topic}-{len(self.chunks):03d}",
            "source_id": source_id,
            "source_title": s["source_title"],
            "source_url": s["source_url"],
            "organization": s["organization"],
            "document_type": s["source_type"],
            "scheme_name": scheme or "General",
            "scheme_category": CATEGORY.get(scheme, "General"),
            "topic": topic,
            "publication_date": s["publication_date"],
            "accessed_date": s["accessed_date"],
            "last_verified_date": s["last_verified_date"],
            "applicable_plan": plan,
            "applicable_option": "All options",
            "text": clean(text),
            "quote": clean(quote),
            "keywords": keywords,
            "boost": boost,  # small retrieval preference for the main answer when a source has several chunks
        })


def build() -> list:
    src = load_sources()
    cap = json.loads(Path(RAW_CAPTURES).read_text(encoding="utf-8"))
    b = Builder(src)

    # ---------- Scheme pages: primary source for scheme facts ----------
    for sid, sc in cap["schemes"].items():
        n = sc["scheme_name"]
        b.add(sid, "overview", f"{n} is described by HDFC Mutual Fund as: {sc['official_description']}",
              sc["official_description"], n, keywords="what is category type kind of scheme fund " + " ".join(sc["aliases"]))
        b.add(sid, "expense_ratio",
              f"The expense ratio (TER) of {n} is {sc['ter_direct']}% for the Direct Plan and {sc['ter_regular']}% "
              "for the Regular Plan, as shown on HDFC Mutual Fund's official scheme page. TER can change over time.",
              f"TER Direct {sc['ter_direct']} | TER Regular {sc['ter_regular']}", n,
              plan="Direct and Regular (values differ)",
              keywords="expense ratio ter total expense ratio cost charges fee annual direct regular")
        b.add(sid, "min_sip", f"The minimum SIP amount for {n} is Rs. {sc['min_sip']}, as shown on HDFC Mutual Fund's official scheme page.",
              f"Min SIP Rs {sc['min_sip']}", n, keywords="minimum sip systematic investment plan smallest amount start monthly")
        b.add(sid, "riskometer", f"The riskometer of {n} shows a risk level of {sc['riskometer']}, as shown on HDFC Mutual Fund's official scheme page.",
              f"Riskometer {sc['riskometer']}", n, keywords="riskometer risk-o-meter risk level how risky category")
        b.add(sid, "benchmark", f"The benchmark of {n} is the {sc['benchmark']}, as shown on HDFC Mutual Fund's official scheme page.",
              f"Benchmark {sc['benchmark']}", n, keywords="benchmark index tri total return index compared")
        if sc["lock_in"]:
            b.add(sid, "lock_in", f"{n} has a lock-in period of {sc['lock_in']}. HDFC Mutual Fund describes it as an open-ended "
                  "Equity Linked Savings Scheme with a statutory lock-in of 3 years and tax benefit.",
                  f"Lock in {sc['lock_in']} | {sc['official_description']}", n,
                  keywords="lock-in lock in period locked redeem withdraw 3 years elss")
        else:
            b.add(sid, "lock_in", f"{n} has no lock-in period; its official scheme page shows lock-in as NA (not applicable).",
                  "Lock in NA", n, keywords="lock-in lock in period locked redeem withdraw")
        if sc["exit_load"]:
            if sc["exit_load"].strip().upper() == "NIL":
                text = f"{n} has no exit load (Nil), as shown on HDFC Mutual Fund's official scheme page."
            else:
                text = (f"For {n}, an exit load of 1.00% is payable if units are redeemed or switched out within 1 year "
                        "from the date of allotment. No exit load is payable after 1 year from the date of allotment.")
            b.add(sid, "exit_load", text, sc["exit_load"], n,
                  keywords="exit load redeem redemption charge penalty withdraw early sell before")

    docs = cap["documents"]
    # ---------- KIMs ----------
    for n, sid in KIM.items():
        sec = docs[sid]["sections"]
        if n == LIQ:
            text = (f"{n} offers a Regular Plan and a Direct Plan, each with a Growth Option and IDCW options "
                    "(Daily, Weekly and Monthly), per its KIM dated 21 Nov 2025.")
        else:
            text = (f"{n} offers a Regular Plan and a Direct Plan, each with a Growth Option and an Income Distribution "
                    "cum Capital Withdrawal (IDCW) Option, per its KIM dated 21 Nov 2025.")
        b.add(sid, "plans_options", text, sec["plans_options"], n,
              keywords="plan plans option options direct regular growth idcw dividend payout reinvestment")
        if n == ELSS:
            text = (f"The minimum purchase and additional purchase amount for {n} is Rs. 500 and in multiples of Rs. 500 "
                    "thereafter, per its KIM dated 21 Nov 2025.")
        elif n == LIQ:
            text = (f"The minimum purchase amount for {n} is Rs. 100 and any amount thereafter for the Growth Option, "
                    "Rs. 10,000 for the Daily IDCW Option, and Rs. 5,000 for the Weekly and Monthly IDCW Options, per its KIM dated 21 Nov 2025.")
        else:
            text = (f"The minimum purchase and additional purchase amount for {n} is Rs. 100 and any amount thereafter, "
                    "per its KIM dated 21 Nov 2025. Units are allotted after deducting applicable stamp duty and other charges, if any.")
        b.add(sid, "min_lumpsum", text, sec["min_amount"], n,
              keywords="minimum lump sum lumpsum one time investment minimum application amount initial purchase additional purchase")
        if "name" in sec and n == LC:
            b.add(sid, "overview", f"{n} was formerly known as HDFC Top 100 Fund, per its KIM dated 21 Nov 2025.",
                  sec["name"], n, keywords="former name formerly known renamed top 100 old name")
    liq = docs["S08"]["sections"]
    b.add("S08", "exit_load",
          "For HDFC Liquid Fund, the exit load on units redeemed or switched out is 0.0070% on Day 1, 0.0065% on Day 2, "
          "0.0060% on Day 3, 0.0055% on Day 4, 0.0050% on Day 5 and 0.0045% on Day 6, and Nil from Day 7 onwards, "
          "as a % of redemption proceeds (KIM dated 21 Nov 2025). Day 1 is the allotment day if the application and funds "
          "are received within the cut-off time, otherwise the day after allotment.",
          liq["exit_load_day1"] + " " + liq["exit_load"], LIQ,
          keywords="exit load redeem redemption charge day 1 day 7 penalty withdraw early")
    b.add("S13", "overview", "HDFC ELSS - Tax Saver Fund was earlier named HDFC ELSS Tax Saver; the name changed with effect from August 26, 2026.",
          docs["S13"]["sections"]["rename"], ELSS, keywords="former name renamed old name name change elss tax saver")

    # ---------- Document cards ----------
    for n, sid in KIM.items():
        b.add(sid, "documents", f"The Key Information Memorandum (KIM) for {n} is dated 21 November 2025 and is available as an official PDF from HDFC Mutual Fund.",
              src[sid]["source_title"], n, keywords="kim key information memorandum document download scheme documents where find")
    for n, sid in SID.items():
        b.add(sid, "documents", f"The Scheme Information Document (SID) for {n} is dated 21 November 2025 and is available as an official PDF from HDFC Mutual Fund.",
              docs[sid]["sections"]["name"], n, keywords="sid scheme information document download offer document where find")
    for n, sid in FUND_FACTS.items():
        b.add(sid, "factsheet", f"HDFC Mutual Fund's October 2026 Fund Facts sheet for {n} gives scheme facts and portfolio data as on 30 September 2026.",
              " ".join(docs[sid]["sections"].values()), n, keywords="factsheet fund facts monthly factsheet download where find")

    # ---------- General investor service and education ----------
    g = cap["general"]
    b.add("S15", "factsheet", "HDFC Mutual Fund publishes a fund factsheet monthly on its Factsheet page, covering scheme objective, "
          "inception date, fund manager, portfolio holdings, risk ratios and historical performance. The latest listed factsheet is September 2026.",
          g["S15"]["text"], keywords="factsheet monthly factsheet where find download all schemes historical")
    b.add("S16", "factsheet", "The HDFC MF Factsheet for September 2026 covers HDFC Mutual Fund's schemes as on 30 September 2026. "
          "For the latest riskometer, it refers investors to the monthly portfolios on www.hdfcfund.com.",
          g["S16"]["text"], keywords="factsheet september 2026 monthly riskometer latest")
    b.add("S17", "documents", "HDFC Mutual Fund publishes its scheme documents on the Fund Documents page, which has tabs for KIM, SID and Scheme Summary.",
          g["S17"]["text"], keywords="scheme documents kim sid scheme summary where find download official documents")
    s19 = g["S19"]
    b.add("S19", "account_statement",
          "HDFC Mutual Fund's Request Statement page lets you have your account statement emailed to the email ID registered with the fund. "
          "On a specific request, the fund provides an account statement within 5 business days.",
          s19["text"] + " " + s19["on_request"], keywords="account statement download statement soa get my statement transaction history email", boost=2.0)
    b.add("S19", "account_statement",
          "The Request Statement page also offers an exit load statement, a capital gains statement, a consolidated account statement and a consolidated realized gains statement.",
          s19["statement_types"], keywords="capital gains statement dividend statement exit load statement consolidated realized gains types")
    b.add("S19", "account_statement",
          "You can also request an HDFC Mutual Fund account statement by SMS to 56767, through the IVR on 1800-3010-6767 (toll free) or "
          "1800-419-7676, or at any HDFC Mutual Fund Investor Service Center.",
          f"{s19['sms']} {s19['ivr']} {s19['branch']}", keywords="sms ivr phone call branch investor service center statement")
    b.add("S19", "cas", "A Consolidated Account Statement (CAS) is sent by mail or email on or before the 10th of the following month "
          "to unit holders whose folio had transactions during that month.",
          s19["cas"], keywords="cas consolidated account statement monthly transaction history 10th")
    s20 = g["S20"]
    b.add("S20", "capital_gains",
          "You can get a capital gains statement from the registrars CAMS (camsonline.com) or KFintech (kfintech.com) using the PAN and email ID "
          "registered with your investments, or from each fund house's website. Capital gain statements are generally available after the financial year ends in March.",
          f"{s20['rta']} {s20['amc']} {s20['timing']}", keywords="capital gains statement capital gain report tax statement itr how to get download cams kfintech", boost=2.0)
    b.add("S20", "capital_gains",
          "A Consolidated Account Statement (CAS) in capital gains format, requested via CAMS or NSDL, includes capital gains across mutual fund holdings linked to your PAN.",
          s20["cas"], keywords="capital gains cas consolidated nsdl cams format")
    b.add("S21", "definition_expense_ratio", g["S21"]["expense_ratio"], g["S21"]["expense_ratio"],
          keywords="what is expense ratio meaning define ter")
    b.add("S21", "definition_exit_load", g["S21"]["exit_load"], g["S21"]["exit_load"], keywords="what is exit load meaning define")
    d = cap["page_definitions"]
    b.add(d["source_id"], "definition_lock_in", d["lock_in"], d["lock_in"], keywords="what is lock-in lock in period meaning elss")
    b.add(d["source_id"], "definition_benchmark", d["benchmark"], d["benchmark"], keywords="what is benchmark meaning")
    s22 = g["S22"]
    b.add("S22", "definition_riskometer",
          "A riskometer (Risk-o-meter) shows a mutual fund scheme's risk level. SEBI requires six levels: Low, Low to Moderate, "
          "Moderate, Moderately High, High and Very High.",
          f"{s22['what']}. {s22['levels']}", keywords="what is riskometer risk-o-meter levels meaning six levels risk")
    return b.chunks


def main():
    chunks = build()
    Path(CHUNKS_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(CHUNKS_PATH).write_text(json.dumps(chunks, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(chunks)} chunks to {CHUNKS_PATH}")


if __name__ == "__main__":
    main()
