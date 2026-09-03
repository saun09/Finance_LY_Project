"""Baseline retrieval: plain TF-IDF cosine similarity over the filing corpus.

No knowledge of company identity, filing date, or filing type — purely a
text-similarity ranking. This exists as the comparison point for the
constrained system in retrieval_constrained.py.
"""

from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.corpus import Filing


@dataclass(frozen=True)
class ScoredFiling:
    filing: Filing
    score: float


class TfidfRetriever:
    """Fits a single TF-IDF space over the whole corpus once, then scores
    arbitrary query strings against it (so a rumour's vector is comparable
    to filing vectors without re-fitting per query)."""

    def __init__(self, corpus: list[Filing]):
        self.corpus = corpus
        self._vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        self._matrix = self._vectorizer.fit_transform([f.filing_text for f in corpus])

    def search(self, query_text: str, top_k: int = 5) -> list[ScoredFiling]:
        query_vec = self._vectorizer.transform([query_text])
        scores = cosine_similarity(query_vec, self._matrix)[0]
        ranked = sorted(zip(self.corpus, scores), key=lambda pair: pair[1], reverse=True)
        return [ScoredFiling(filing=f, score=float(s)) for f, s in ranked[:top_k]]
