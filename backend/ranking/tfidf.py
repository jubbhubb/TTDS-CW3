import math
from core.models import Document, SearchResult
from ranking.base import RankingStrategy
import time


class TFIDFRanking(RankingStrategy):

    def _compute_tfd(self, tf: int) -> float:
        if tf == 0:
            return 0.0
        return 1.0 + math.log10(tf)

    def _compute_idf(self, doc_frequency: int, total_docs: int) -> float:
        if doc_frequency == 0:
            return 0.0
        return math.log10(total_docs / doc_frequency)

    def _compute_score(self, tf: int, doc_frequency: int, total_docs: int) -> float:
        return self._compute_tfd(tf) * self._compute_idf(doc_frequency, total_docs)

    def score_documents(self, query_terms, candidate_docs, index, posting_lists=None) -> tuple[dict, float]:
        numberOfDocs = index.doc_count
        print(f"  [TFIDF DEBUG] scoring {len(candidate_docs)} docs, posting_lists provided: {posting_lists is not None}")
        if candidate_docs and query_terms:
            first_doc = candidate_docs[0]
            first_term = query_terms[0]
            using_pl = posting_lists is not None and first_term in posting_lists
            print(f"  [TFIDF DEBUG] first doc={first_doc.id}, first term={first_term}, using posting_lists={using_pl}")

        tfidf_lookup = {}
        max_tfidf = 0

        df_cache = {}
        for term in query_terms:
            if posting_lists and term in posting_lists:
                df_cache[term] = posting_lists[term].doc_frequency()
            else:
                df_cache[term] = index.doc_frequency(term)

        t_get = 0
        t_score = 0

        for doc in candidate_docs:
            total_score = 0
            term_scores = {}
            term_positions = {}

            for term in query_terms:
                t0 = time.perf_counter()
                if posting_lists and term in posting_lists:
                    entry = posting_lists[term].get(doc.id)
                    positions = entry.positions if entry else []
                else:
                    positions = index.term_positions(term, doc.id)
                t_get += time.perf_counter() - t0

                t0 = time.perf_counter()
                tf = len(positions)
                df = df_cache[term]
                term_score = self._compute_score(tf, df, numberOfDocs)
                t_score += time.perf_counter() - t0

                term_scores[term] = term_score
                term_positions[term] = positions
                total_score += term_score

            if term_scores:
                best_term = max(term_scores, key=term_scores.get)
                best_term_score = term_scores[best_term]
            else:
                best_term = None
                best_term_score = 0

            tfidf_lookup[doc.id] = {
                'doc_id': doc.id,
                'total_score': total_score,
                'best_term': best_term,
                'best_term_score': best_term_score,
                'term_scores': term_scores,
                'term_positions': term_positions
            }

            if total_score > max_tfidf:
                max_tfidf = total_score

        print(f"  [TFIDF DEBUG] t_get={t_get*1000:.1f}ms t_score={t_score*1000:.1f}ms")

        if max_tfidf == 0:
            max_tfidf = 1

        return tfidf_lookup, max_tfidf
    def rank(self, query_tokens, candidate_docs, index) -> list[SearchResult]:
        tfidf_lookup, _ = self.score_documents(query_tokens, candidate_docs, index)
        results = []
        for doc in candidate_docs:
            score = tfidf_lookup[doc.id]['total_score']
            results.append(SearchResult(document=doc, score=score))
        results.sort(key=lambda r: r.score, reverse=True)
        return results