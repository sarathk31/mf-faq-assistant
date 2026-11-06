"""Write sample_qa.md from real assistant output (offline pipeline, or --url for the live app)."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from evaluation.run_eval import ask_live  # noqa: E402

QUESTIONS = [
    ("What is the exit load for HDFC Liquid Fund?", "Direct factual"),
    ("What is the expense ratio of HDFC Flexi Cap Fund?", "Direct factual"),
    ("What is the lock-in period for HDFC ELSS - Tax Saver Fund?", "Direct factual"),
    ("How can I get a capital gains statement?", "Investor service"),
    ("How can I download my account statement?", "Investor service"),
    ("What is a riskometer?", "Educational"),
    ("What is the minimum amount?", "Ambiguous"),
    ("What is the NAV of HDFC Flexi Cap Fund today?", "Unsupported"),
    ("Should I invest in HDFC Flexi Cap Fund?", "Advice refusal"),
    ("Which scheme will give me the highest return?", "Performance refusal"),
]
KIND = {"factual": "Factual", "clarification": "Clarification", "refusal": "Refusal", "not_found": "Not found"}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--url"); args = ap.parse_args()
    if not args.url:
        from rag.pipeline import answer_question
    mode = f"live app ({args.url})" if args.url else "offline pipeline, extractive generation (run without a Groq key)"
    out = ["# Sample Q&A", "", f"Real responses produced by the assistant. Mode: {mode}.", ""]
    for i, (q, cat) in enumerate(QUESTIONS, 1):
        r = ask_live(args.url, q) if args.url else answer_question(q)
        out += [f"## {i}. {q}", "", f"- **Category:** {cat} (classified as `{r['category']}`)",
                f"- **Response type:** {KIND.get(r['status'], r['status'])}", f"- **Assistant:** {r['answer']}",
                f"- **Source:** {('[' + r['source_title'] + '](' + r['source_url'] + ')') if r.get('source_url') else 'None (no link for this response type)'}",
                f"- **{r['last_updated'] or 'Last updated from sources: n/a'}**", ""]
    (ROOT / "sample_qa.md").write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out[:12]))


if __name__ == "__main__":
    main()
