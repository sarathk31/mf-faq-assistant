"""Run the evaluation set and write evaluation/evaluation_results.md.

Offline (default): calls the pipeline directly. With no GROQ_API_KEY the generator uses its
grounded extractive fallback, so results reflect classification, retrieval, evidence checks,
refusals and citations, not LLM wording.

Live:  python evaluation/run_eval.py --url https://<your-app>.vercel.app
       calls the deployed /api/ask endpoint (LLM included).
"""
import argparse
import csv
import json
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def ask_live(url, q):
    req = urllib.request.Request(url.rstrip("/") + "/api/ask", data=json.dumps({"question": q}).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url")
    ap.add_argument("--out", default=str(ROOT / "evaluation" / "evaluation_results.md"))
    args = ap.parse_args()
    cases = json.loads((ROOT / "evaluation" / "sample_questions.json").read_text())
    sources = {r["source_url"] for r in csv.DictReader(open(ROOT / "data" / "sources.csv", encoding="utf-8"))}
    if not args.url:
        from rag.pipeline import answer_question
    rows, by_group = [], defaultdict(lambda: [0, 0])
    m = defaultdict(lambda: [0, 0])
    for c in cases:
        r = ask_live(args.url, c["question"]) if args.url else answer_question(c["question"])
        cat_ok = r.get("category") == c["category"]
        status_ok = r.get("status") == c["status"]
        content_ok = all(s.lower() in (r.get("answer") or "").lower() for s in c.get("must_contain", []))
        leak_ok = all(s not in (r.get("answer") or "") for s in c.get("must_not_contain", []))
        scheme_ok = (r.get("status") != "factual") or (c.get("scheme") in (None, r.get("scheme")))
        cite_ok = (r.get("status") != "factual") or (r.get("source_url") in sources and bool(r.get("last_updated")))
        passed = all([cat_ok, status_ok, content_ok, leak_ok, scheme_ok, cite_ok])
        by_group[c["group"]][0] += passed
        by_group[c["group"]][1] += 1
        m["classification accuracy"][0] += cat_ok; m["classification accuracy"][1] += 1
        if c["status"] == "factual":
            m["retrieval relevance (right scheme & topic)"][0] += scheme_ok and status_ok; m["retrieval relevance (right scheme & topic)"][1] += 1
            m["factual correctness (expected values present)"][0] += content_ok and status_ok; m["factual correctness (expected values present)"][1] += 1
            m["citation availability & correctness"][0] += cite_ok and status_ok; m["citation availability & correctness"][1] += 1
        if c["status"] in ("not_found", "clarification"):
            m["no hallucinated answer on unsupported/ambiguous"][0] += r.get("status") != "factual"; m["no hallucinated answer on unsupported/ambiguous"][1] += 1
        if c["group"] == "F. Advice":
            m["advice/performance refusal consistency"][0] += r.get("status") == "refusal"; m["advice/performance refusal consistency"][1] += 1
        if c["group"] == "G. PII and security":
            m["PII / security handling"][0] += r.get("status") == "refusal" and leak_ok; m["PII / security handling"][1] += 1
        rows.append((c, r, passed))

    mode = f"live API at {args.url}" if args.url else "offline pipeline (no LLM key: extractive generation)"
    lines = [f"# Evaluation results", "", f"- Run: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
             f"- Mode: {mode}", f"- Questions: {len(rows)}; passed: {sum(p for *_, p in rows)}", "",
             "## Metrics", "", "| Metric | Result |", "|---|---|"]
    for k, (a, n) in m.items():
        lines.append(f"| {k} | {a}/{n} |")
    lines += ["", "## By group", "", "| Group | Passed |", "|---|---|"]
    for g, (a, n) in by_group.items():
        lines.append(f"| {g} | {a}/{n} |")
    lines += ["", "## Every question", "", "| ID | Question | Expected | Got | Pass | Answer (first 140 chars) | Source |", "|---|---|---|---|---|---|---|"]
    for c, r, p in rows:
        ans = (r.get("answer") or "").replace("|", "/")[:140]
        src = r.get("source_title") or "-"
        lines.append(f"| {c['id']} | {c['question']} | {c['category']} / {c['status']} | {r.get('category')} / {r.get('status')} | {'yes' if p else 'NO'} | {ans} | {src} |")
    Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:20]))


if __name__ == "__main__":
    main()
