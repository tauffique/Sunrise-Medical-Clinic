"""Dependency-free retriever for the chatbot's RAG step.

Documents are indexed with TF-IDF weights and ranked by cosine similarity.
If the knowledge base grows, swap this for embeddings and a vector store.
"""
import math
import re
from collections import Counter

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "is", "are", "was", "were", "be", "to",
    "of", "in", "on", "at", "for", "with", "i", "my", "me", "it", "its", "this",
    "that", "have", "has", "had", "do", "does", "so", "if", "as", "by", "from",
    "about", "what", "how", "can", "been", "since", "some", "very", "just", "am",
    "when", "your", "you", "we", "our", "they", "there", "any", "will",
}

_WORD_RE = re.compile(r"[a-zäöüß]+")  # includes German umlauts, so 'rücken' stays one word


def _stem(word):
    """Very small stemmer: 'headaches' -> 'headache', 'injuries' -> 'injury'."""
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def tokenize(text):
    return [
        _stem(w)
        for w in _WORD_RE.findall(text.lower())
        if w not in STOPWORDS and len(w) > 1
    ]


class KnowledgeIndex:
    """TF-IDF index over knowledge documents.

    Each document is a dict with at least: id, type, title, text.
    Optional: keywords (list[str]), specialty (str).
    """

    def __init__(self, documents):
        self.documents = list(documents)
        df = Counter()
        term_counts = []
        for doc in self.documents:
            text = " ".join([doc["title"], doc["text"], " ".join(doc.get("keywords", []))])
            tf = Counter(tokenize(text))
            term_counts.append(tf)
            df.update(tf.keys())
        n = len(self.documents)
        self._idf = {t: math.log((1 + n) / (1 + f)) + 1.0 for t, f in df.items()}
        self._vectors = [self._vectorize(tf) for tf in term_counts]

    def _vectorize(self, tf):
        vec = {t: c * self._idf[t] for t, c in tf.items() if t in self._idf}
        norm = math.sqrt(sum(w * w for w in vec.values())) or 1.0
        return {t: w / norm for t, w in vec.items()}

    def search(self, query, k=3, min_score=0.05):
        qvec = self._vectorize(Counter(tokenize(query)))
        scored = []
        for doc, dvec in zip(self.documents, self._vectors):
            score = sum(w * dvec.get(t, 0.0) for t, w in qvec.items())
            if score >= min_score:
                scored.append((score, doc))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [dict(doc, score=round(score, 3)) for score, doc in scored[:k]]