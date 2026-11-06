# Scheme Facts: a facts-only mutual fund FAQ assistant

A small retrieval-augmented assistant that answers factual questions about four HDFC Mutual Fund schemes, using only
official public sources. Every answer is at most three sentences, carries exactly one official source link, and shows when
the sources were last verified. It refuses investment advice and never handles personal information.

NextLeap milestone: *AI System Design, LLMs & Prompt Engineering*. Product context: **Groww**.

- **Live app:** _add the Vercel URL after deployment_
- **Sources:** [`data/sources.csv`](data/sources.csv) · [`data/sources.md`](data/sources.md)
- **Sample Q&A:** [`sample_qa.md`](sample_qa.md)
- **Architecture:** [`docs/architecture.md`](docs/architecture.md)

## 1. Problem

Retail investors on platforms like Groww ask the same factual questions again and again: What is the exit load? What's the
minimum SIP? Is there a lock-in? How do I get my capital gains statement? The answers sit in long PDFs (SIDs, KIMs, factsheets)
and service pages. Generic chatbots answer them from memory, mix up schemes and plans, and drift into advice. This assistant
answers only from verified official documents, shows the source, and declines anything that would be advice.

This is an independent study prototype. It is not affiliated with, or integrated into, Groww or HDFC Mutual Fund, and has no
access to any investor account.

## 2. Scope

| | |
|---|---|
| **Product context** | Groww: retail direct-plan investors (chosen over INDmoney, Kuvera, PowerUp Money and Wealth Monitor; see the decision matrix in `docs/`) |
| **AMC** | HDFC Mutual Fund |
| **Schemes** | HDFC Large Cap Fund · HDFC Flexi Cap Fund · HDFC ELSS - Tax Saver Fund · HDFC Liquid Fund |
| **Answers** | Expense ratio (TER, Direct and Regular), exit load, minimum SIP, minimum lump sum, lock-in, riskometer, benchmark, plans and options, former names, where to find the SID/KIM/factsheet, account statements, CAS, capital gains statements, and definitions (expense ratio, exit load, lock-in, riskometer, benchmark) |
| **Refuses** | Buy/sell/switch/stop advice, suitability, comparisons of which is "better", returns and NAV predictions, personal account questions |
| **Not found** | NAV, AUM values, holdings, fund managers, tax rates, any scheme outside the four above |

## 3. Source policy

Only official public sources are used: HDFC Mutual Fund's scheme pages, KIMs, SIDs, factsheets, TER disclosure and investor-service
pages, plus a SEBI circular. No blogs, aggregators, forums or search snippets. There are 22 sources in total, each with a reason for
inclusion, document date and verification date in `data/sources.csv`.

| Type | Count |
|---|---|
| Official scheme pages | 4 |
| KIMs | 4 |
| SIDs | 2 |
| Scheme factsheets (Fund Facts) + monthly factsheet | 5 |
| Factsheet page, fund documents page, TER report | 3 |
| Investor-service and investor-education pages | 3 |
| SEBI circular (riskometer) | 1 |

When sources disagree, the scheme-specific document wins over general guidance. Five conflicts were found and resolved; they are
listed in `data/sources.md`. For example, a general HDFC blog says liquid funds have no exit load, while HDFC Liquid Fund's own KIM shows
a day-wise exit load. The KIM is used.

## 4. Architecture

```
Question → Input validation → Classification → Scope / safety decision → Retrieval
        → Evidence check → LLM generation → Answer + citation validation → Response
```

- **Input validation:** rejects empty or very long input.
- **Classification:** rule-based, with safety checks first (PII, prompt reveal, advice, performance), then scope, topic and ambiguity.
  A scheme name inside an advice question never makes it a factual query.
- **Retrieval:** BM25 over 62 single-fact chunks, filtered by scheme and topic, so no cross-scheme mixing.
- **Evidence check:** the top chunk must match the requested scheme and topic and pass a score threshold. Otherwise the assistant says it couldn't verify the detail.
- **Generation:** Groq LLM, temperature 0, evidence-only system prompt (`rag/system_prompt.py`), at most three sentences, no links.
- **Validation:** rejects answers with URLs, advice wording, more than three sentences, or numbers not in the evidence. On rejection or LLM
  failure, it falls back to the verified chunk text. The single source link is attached by code from chunk metadata.

Details: [`docs/architecture.md`](docs/architecture.md).

## 5. Technology

- Python 3.10+ standard library only at runtime (BM25 and the Groq HTTP call). No vector database, no framework.
- Groq API (OpenAI-compatible chat completions), model set by `GROQ_MODEL`.
- Vercel: a static `index.html` plus two Python serverless functions: `api/ask.py` (answers) and `api/schemes.py` (fund cards).
- App-style HTML/CSS/JS interface (`index.html`, no framework): an Explore page with category filters, a page per fund (key facts with a Direct/Regular toggle, an animated SEBI riskometer, official documents, common questions), a search bar that also sends questions to the assistant, light/dark theme, and an assistant panel that becomes a bottom sheet on mobile. Fund pages use the same verified chunks as the answers (`rag/fund_cards.py`). No NAV or returns are shown.
- Speed: the page wakes the serverless function on load (`GET /api/ask`), the corpus is loaded at import, repeated questions are answered from an in-page cache, the LLM call times out after 8 seconds and falls back to the verified source text, and the assistant shows its progress while it works. Personal details (PAN, Aadhaar, phone, email, OTP, folio numbers) are caught in the browser and never sent.
- pytest for tests.

## 6. Run locally

```bash
git clone <your-repo-url>
cd mf-faq-assistant
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt  # only pytest; the app itself needs no packages
cp .env.example .env                 # then put your Groq key in .env
python -m ingestion.build_corpus     # rebuilds data/processed/chunks.json from the verified captures
python dev_server.py                 # open http://localhost:8000
```

Without a key, the app still works in extractive mode: answers are the verified source sentences.

Tests and evaluation:

```bash
python -m pytest -q
python evaluation/run_eval.py                       # offline
python evaluation/run_eval.py --url https://<app>.vercel.app   # live, includes the LLM
```

## 7. Deploy to Vercel

1. Push this folder to a GitHub repository (the web uploader works too).
2. On vercel.com: **Add New → Project → Import** the repository. Framework preset: **Other**. No build command.
3. **Settings → Environment Variables:** add `GROQ_API_KEY` (and optionally `GROQ_MODEL`). Redeploy.
4. Open the URL and ask a question. `/api/ask` accepts `POST {"question": "..."}`.

## 8. Sample questions

| Question | Behaviour |
|---|---|
| What is the exit load for HDFC Liquid Fund? | Day-wise exit load from the KIM, with the KIM linked |
| What is the expense ratio of HDFC Flexi Cap Fund? | Direct 0.75%, Regular 1.35%, with the scheme page linked |
| What is the lock-in for HDFC ELSS - Tax Saver Fund? | 3 years |
| How can I get a capital gains statement? | CAMS / KFintech / AMC routes, with HDFC's guide linked |
| What is a riskometer? | SEBI's six levels, with the SEBI circular linked |
| What is its expense ratio? | Asks which scheme |
| What is the NAV of HDFC Flexi Cap today? | Not in sources; links the scheme page |
| Should I invest in HDFC Flexi Cap Fund? | Polite refusal; links the KIM |
| My PAN is ... | Privacy refusal; nothing echoed |

Full real outputs: [`sample_qa.md`](sample_qa.md). Test results: [`evaluation/evaluation_results.md`](evaluation/evaluation_results.md) and [`evaluation/holdout_log.md`](evaluation/holdout_log.md).

## 9. Disclaimer

This assistant provides factual information from a limited collection of official public mutual fund sources. It does not provide
investment advice, recommendations, return predictions or personalized financial guidance. Information may change, so users should
verify details against the latest official scheme documents. Do not enter PAN, Aadhaar, account numbers, OTPs or other personal information.

## 10. Known limitations

- **Coverage:** one AMC and four schemes only.
- **Freshness:** facts were verified on 4 Nov 2026. TER and riskometer change monthly, and nothing updates automatically.
- **Capture method:** sources were captured through a browser because the development network blocked AMC sites (see `docs/capture_and_verification.md`).
- **Partial documents:** SIDs are only partly ingested, and minimum lump-sum amounts come from KIMs dated 21 Nov 2025.
- **Retrieval:** rule-based classification and keyword retrieval can miss unusual phrasings; the response is then a clarification or "not found", not a guess.
- **LLM:** wording can vary. The validator blocks new numbers, links and advice, but cannot judge every nuance.
- **No accounts or transactions:** the assistant has no access to investor accounts and cannot transact.

## 11. Future improvements

- Scheduled re-verification of sources, with a diff report when a value changes.
- A semantic retrieval layer for paraphrases, kept behind the same evidence check.
- More schemes and AMCs, with a source registry per AMC.
- Showing the document's own "as of" date next to each value (for example, TER as of a specific month).
