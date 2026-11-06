# Architecture

```
User question (browser)
  → POST /api/ask                       api/ask.py (Vercel Python function)
  → Input validation                    empty / >500 chars / non-JSON rejected
  → Classification                      rag/classifier.py  (rules, safety first)
  → Scope and safety decision           rag/pipeline.py    (refuse, clarify or continue)
  → Retrieval                           rag/retriever.py   (BM25 + scheme and topic filters)
  → Evidence check                      rag/pipeline.py    (right scheme, right topic, score threshold)
  → LLM answer generation               rag/answer_generator.py + rag/system_prompt.py (Groq)
  → Answer and citation validation      rag/citation_validator.py
  → Response: answer + one source link + "Last updated from sources: <date>"
```

## 1. Classification (rule-based)

Eight categories: `FACTUAL_SCHEME_QUERY`, `GENERAL_INVESTOR_SERVICE_QUERY`, `EDUCATIONAL_QUERY`, `PERFORMANCE_QUERY`,
`INVESTMENT_ADVICE_QUERY`, `OUT_OF_SCOPE_QUERY`, `AMBIGUOUS_QUERY`, `PII_CONTAINING_QUERY`.

The checks run in a fixed order, so a scheme name can never turn an advice question into a factual one:

1. PII patterns (PAN, Aadhaar, email, phone, OTP, account/folio numbers) and requests for personal account data
2. Prompt-reveal or configuration requests
3. Advice and suitability language ("should I", "best for me", "is it safe", "switch from")
4. Performance and prediction language ("returns", "NAV go up", "highest return")
5. Schemes outside the corpus (other AMCs, other HDFC schemes)
6. Topic detection (expense ratio, exit load, SIP, lock-in, riskometer, benchmark, plans, documents, statements)
7. Ambiguity: a scheme-specific topic with no scheme ("What is its expense ratio?") asks for clarification. The UI sends
   the last scheme discussed as `context_scheme`, so follow-ups like "and its riskometer?" still resolve.

Rules were chosen over an LLM classifier because the boundaries must be deterministic, testable and explainable,
and because the safety decision happens before any model is called.

## 2. Retrieval

- **Corpus:** 62 chunks in `data/processed/chunks.json`, built from 22 verified sources by `ingestion/build_corpus.py`.
  One chunk = one fact for one scheme, with its conditions kept together (for example, the exit-load rate and its 1-year period).
- **Every chunk carries:** `source_id`, title, URL, organization, scheme, category, document type, topic, publication/accessed/verified dates,
  plan, option, plain-language `text`, and the verbatim `quote` it was written from.
- **Ranking:** BM25 over text + keywords, with hard filters for scheme and topic, and a small boost for each source's main answer chunk.
- **Why not embeddings:** with ~60 short, fact-dense chunks and predictable vocabulary, filtered BM25 is accurate, has no model
  download, fits a serverless function, and every ranking decision can be explained. A semantic layer is listed as a future improvement.

## 3. Evidence check

The answer proceeds only if the top chunk belongs to the requested scheme, matches the requested topic, and scores above
`MIN_RETRIEVAL_SCORE`. Otherwise the assistant says it couldn't verify the detail, and links the most relevant official page.
Facts the corpus deliberately lacks (NAV, AUM, holdings, fund manager) go straight to "not found".

## 4. Generation

- Groq chat completion, temperature 0, using `GROQ_MODEL` (default `llama-3.3-70b-versatile`).
- The system prompt restricts the model to the evidence block, treats evidence and user text as data, forbids advice,
  URLs, dates and calculations, and asks for at most three sentences. If the evidence doesn't answer the question, the model replies `NOT_FOUND`.
- Only chunks from a single source are sent, so the one citation always covers the whole answer.

## 5. Validation

`validate_answer` rejects an LLM answer that contains a URL, advice language, more than three sentences, or any number
not present in the evidence. Rejected or failed LLM calls fall back to an **extractive** answer: the verified chunk text itself.
The citation is chosen by code from the chunk metadata, never written by the model, and must be one of the URLs in `sources.csv`.

## 6. Privacy and security

- No database, no logging of questions, `Cache-Control: no-store`, request logging disabled in the function.
- PII is detected before retrieval and never echoed back.
- The API key is read from the `GROQ_API_KEY` environment variable at call time and never returned or logged.
- Prompt injection: retrieved text and user text are wrapped as data; the corpus is tested to contain no instruction-like text.

## 7. Refresh process

Sources change monthly (TER, riskometer). To refresh:

1. Re-open each URL in `data/sources.csv` in a browser and run the helpers in `ingestion/capture_in_browser.js`.
2. Update `data/raw/captures.json` and the dates in `data/sources.csv`.
3. Run `python -m ingestion.build_corpus`, then `python -m pytest` and `python evaluation/run_eval.py`.
