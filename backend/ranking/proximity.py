import math

from core.index import PositionalIndex
from core.models import Document, SearchResult
from ranking.base import RankingStrategy


class ProximityBM25Ranking(RankingStrategy):
    """
    Combined BM25 + proximity scoring.

    Final score = BM25_score * (1 + proximity_weight * proximity_score)

    This rewards documents where search terms appear close together,
    similar to Typesense's approach of scoring based on token proximity.
    """

    def __init__(
        self,
        k1: float = 1.5,
        b: float = 0.75,
        proximity_weight: float = 0.5,
    ):
        self.k1 = k1
        self.b = b
        self.proximity_weight = proximity_weight

    def rank(
        self,
        query_tokens: list[str],
        candidate_docs: list[Document],
        index: PositionalIndex,
    ) -> list[SearchResult]:
        avg_dl = index.avg_doc_length

        results = []
        for doc in candidate_docs:
            # --- BM25 component ---
            bm25_score = 0.0
            doc_len = index.doc_length(doc.id)
            for term in query_tokens:
                tf = index.term_frequency(term, doc.id)
                df = index.doc_frequency(term)
                if df > 0:
                    idf = math.log((index.doc_count - df + 0.5) / (df + 0.5) + 1)
                    numerator = tf * (self.k1 + 1)
                    denominator = tf + self.k1 * (1 - self.b + self.b * (doc_len / avg_dl))
                    bm25_score += idf * (numerator / denominator)

            # --- Proximity component ---
            prox_score = index.proximity_score(query_tokens, doc.id)

            # --- Combined score ---
            final_score = bm25_score * (1 + self.proximity_weight * prox_score)

            results.append(SearchResult(
                document=doc,
                score=final_score,
                proximity_score=prox_score,
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results