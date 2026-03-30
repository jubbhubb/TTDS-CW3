import math
from core.models import Document, SearchResult
from ranking.base import RankingStrategy


class BM25Ranking(RankingStrategy):

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b

    def score_documents(self, query_terms, candidate_docs, index, posting_lists=None) -> tuple[dict, float]:
        avg_dl = index.avg_doc_length
        bm25_lookup = {}
        max_bm25 = 0

        # precompute df per term
        df_cache = {}
        for term in query_terms:
            if posting_lists and term in posting_lists:
                df_cache[term] = posting_lists[term].doc_frequency()
            else:
                df_cache[term] = index.doc_frequency(term)

        for doc in candidate_docs:
            total_score = 0
            term_scores = {}
            term_positions = {}
            doc_len = index.doc_length(doc.id)

            for term in query_terms:
                if posting_lists and term in posting_lists:
                    entry = posting_lists[term].get(doc.id)
                    positions = entry.positions if entry else []
                else:
                    positions = index.term_positions(term, doc.id)

                tf = len(positions)
                df = df_cache[term]

                if df > 0:
                    idf = math.log((index.doc_count - df + 0.5) / (df + 0.5) + 1)
                    numerator = tf * (self.k1 + 1)
                    denominator = tf + self.k1 * (1 - self.b + self.b * (doc_len / avg_dl if avg_dl > 0 else 1))
                    term_score = idf * (numerator / denominator)
                else:
                    term_score = 0.0

                term_scores[term] = term_score
                term_positions[term] = positions
                total_score += term_score

            bm25_lookup[doc.id] = {
                'total_score': total_score,
                'term_scores': term_scores,
                'term_positions': term_positions,
            }

            if total_score > max_bm25:
                max_bm25 = total_score

        if max_bm25 == 0:
            max_bm25 = 1

        return bm25_lookup, max_bm25

    def rank(self, query_tokens, candidate_docs, index) -> list[SearchResult]:
        bm25_lookup, _ = self.score_documents(query_tokens, candidate_docs, index)
        results = []
        for doc in candidate_docs:
            score = bm25_lookup[doc.id]['total_score']
            results.append(SearchResult(document=doc, score=score))
        results.sort(key=lambda r: r.score, reverse=True)
        return results