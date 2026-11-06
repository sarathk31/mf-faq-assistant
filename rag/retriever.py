"""BM25 keyword retrieval with metadata filters.

Why not embeddings: the corpus is ~70 short, fact-dense chunks, and questions use
predictable terms (exit load, SIP, TER). BM25 plus scheme/topic filters is
accurate here, fully explainable, and small enough for a serverless function.
"""
import json
import math
import re
from collections import Counter
from functools import lru_cache

from config.settings import CHUNKS_PATH

STOP = set("""a an the is are was were be of for to in on at by with and or what which how do does can i my me
it its this that there their from as about please tell know any much many show give get""".split())


def tokenize(text: str) -> list[str]:
    toks = re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", text.lower())
    return [t for t in toks if t not in STOP]


@lru_cache(maxsize=1)
def load_chunks() -> tuple:
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        return tuple(json.load(f))


class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.4, b: float = 0.75):
        self.docs, self.k1, self.b = docs, k1, b
        self.N = len(docs)
        self.avgdl = sum(len(d) for d in docs) / max(self.N, 1)
        df = Counter(t for d in docs for t in set(d))
        self.idf = {t: math.log(1 + (self.N - n + 0.5) / (n + 0.5)) for t, n in df.items()}
        self.tf = [Counter(d) for d in docs]

    def score(self, query: list[str], i: int) -> float:
        tf, dl, s = self.tf[i], len(self.docs[i]), 0.0
        for t in query:
            if t in tf:
                f = tf[t]
                s += self.idf.get(t, 0) * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / self.avgdl))
        return s


@lru_cache(maxsize=1)
def _index():
    chunks = load_chunks()
    docs = [tokenize(c["text"] + " " + c.get("keywords", "") + " " + c["topic"].replace("_", " ")) for c in chunks]
    return chunks, BM25(docs)


def retrieve(question: str, schemes: list[str] | None = None, topics: list[str] | None = None,
             general_only: bool = False, top_k: int = 3, only_topics: set | None = None) -> list[dict]:
    """Return top chunks with scores.
    Hard filters: scheme, general-only, only_topics. Soft: +5 boost when the chunk topic matches a requested topic."""
    chunks, bm25 = _index()
    q = tokenize(question)
    topics = set(topics or [])
    results = []
    for i, c in enumerate(chunks):
        if schemes and c["scheme_name"] not in schemes:
            continue
        if general_only and c["scheme_name"] != "General":
            continue
        if only_topics is not None and c["topic"] not in only_topics:
            continue
        s = bm25.score(q, i)
        if s > 0:
            s += c.get("boost", 0.0)
        if topics and (c["topic"] in topics or any(c["topic"] == f"definition_{t}" for t in topics)):
            s += 5.0
        if s > 0:
            results.append({**c, "score": round(s, 3)})
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top_k]
