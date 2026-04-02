import re
import math
import time
from core.models import SearchResult
from core.tokenizer import Tokenizer
from core.index import PositionalIndex
from ranking.base import RankingStrategy
from ranking.proximity_helpers import min_ordered_distance, find_ordered_terms
from repository.document_repo import DocumentRepository
from ranking.proximity_ranking import ProximityRanking

from ranking.bm25 import BM25Ranking
from collections import namedtuple
from nltk.corpus import cmudict
import Levenshtein
import debug

class QueryPipeline:
    """Pipeline: Raw Query → Parse → Tokenize → Lookup → Rank → Results"""

    def __init__(
            self,
            tokenizer: Tokenizer,
            index: PositionalIndex,
            repository: DocumentRepository,
            ranker: RankingStrategy,    
    ):
        self.tokenizer = tokenizer
        self.index = index
        self.repository = repository
        self.ranker = ranker
        self.proximity_ranker = ProximityRanking()

    # ── Existing methods unchanged ────────────────────────────

    def search(self,raw_query: str, top_k: int = 5) -> list[SearchResult]:
        phrase_tokens, remaining_query = self._extract_phrases(raw_query)
        query_tokens = self.tokenizer.tokenize(remaining_query)

        phrase_doc_ids: set[str] | None = None
        if phrase_tokens:
            phrase_doc_ids = self.index.phrase_search(phrase_tokens)
            if not phrase_doc_ids:
                return []
            query_tokens = list(dict.fromkeys(query_tokens + phrase_tokens))

        if not query_tokens:
            return []

        candidate_ids: set[str] = set()
        for token in query_tokens:
            candidate_ids |= self.index.lookup(token)

        if phrase_doc_ids is not None:
            candidate_ids &= phrase_doc_ids

        candidates = []
        for doc_id in candidate_ids:
            doc = self.repository.get(doc_id)
            if doc:
                candidates.append(doc)

        ranked = self.ranker.rank(query_tokens, candidates, self.index)

        if phrase_doc_ids is not None:
            for result in ranked:
                if result.document.id in phrase_doc_ids:
                    result.phrase_matched = True

        return ranked[:top_k]



    def _extract_phrases(self, query: str) -> tuple[list[str], str]:
        phrases = re.findall(r'"([^"]+)"', query)
        remaining = re.sub(r'"[^"]*"', "", query).strip()
        phrase_tokens: list[str] = []
        for phrase in phrases:
            phrase_tokens.extend(self.tokenizer.tokenize(phrase))
        return phrase_tokens, remaining

    def _resolve_partial_matches(self, query_terms, max_results=1000, posting_lists=None, candidate_ids=None):
        n = len(query_terms)
        if n == 0:
            return []

        min_matches = max(1, 3 * n // 4)

        # build term→doc_ids from posting_lists in memory
        term_to_docs = {}
        for term in query_terms:
            if posting_lists and term in posting_lists:
                term_to_docs[term] = posting_lists[term]
            else:
                pl = self.index.get_posting_list(term)
                term_to_docs[term] = pl if pl else None

        # count term matches per doc efficiently
        doc_match_count = {}
        for term, pl in term_to_docs.items():
            if pl is None:
                continue
            for entry in pl:
                if candidate_ids and entry.doc_id not in candidate_ids:
                    continue
                doc_match_count[entry.doc_id] = doc_match_count.get(entry.doc_id, 0) + 1

        # group by match count into tiers
        doc_info = {}
        for doc_id, match_count in doc_match_count.items():
            if match_count >= min_matches:
                positions_per_word = []
                for term in query_terms:
                    pl = term_to_docs.get(term)
                    if pl:
                        entry = pl.get(doc_id)
                        positions_per_word.append(entry.positions if entry else [])
                    else:
                        positions_per_word.append([])
                doc_info[doc_id] = {
                    "match_count": match_count,
                    "positions": positions_per_word
                }

        results = []
        total_collected = 0

        for match_count in range(n, min_matches - 1, -1):
            if total_collected >= max_results:
                break
            tier_docs = set()
            tier_positions = {}
            for doc_id, info in doc_info.items():
                if info["match_count"] == match_count:
                    tier_docs.add(doc_id)
                    tier_positions[doc_id] = info["positions"]
                    total_collected += 1
                    if total_collected >= max_results:
                        break
            if tier_docs:
                results.append((tier_docs, tier_positions))

        return results


    def _is_well_formed(self, words) -> bool:
        boolean_terms = {"AND", "OR", "NOT"}

        if not words:
            return False

        if words[-1] in boolean_terms:
            return False

        non_op_count = 0

        for i, tok in enumerate(words):
            if tok in {"AND", "OR"}:
                if i == 0 or words[i - 1] in {"AND", "OR"}:
                    return False
                non_op_count = 0

            elif tok == "NOT":
                if i > 0 and words[i - 1] not in {"AND", "OR"}:
                    return False
                if i == len(words) - 1 or words[i + 1] in {"AND", "OR"}:
                    return False
                non_op_count = 0

            else:
                non_op_count += 1
                if non_op_count > 2:
                    return False

        return True

    def _resolve_term(self, term) -> set:
        # was: self.index[term].keys()
        # now: self.index.lookup(term)
        if isinstance(term, str):
            doc_ids = self.index.lookup(term)
            if not doc_ids:
                print(f"Word '{term}' not in index")
            return doc_ids
        return term  # already a set, pass through

    def boolean_search(self, query, top_k=10) -> list[SearchResult]:
        boolean_terms = {"AND", "OR", "NOT"}


        # Step 1: clean and split
        cleaned = re.sub(r"[^\w\s]", "", query)
        words = cleaned.split()

        # Step 2: build term tokens
        term_tokens = []
        for word in words:
            if word in boolean_terms:
                term_tokens.append(word)
            else:
                stemmed = self.tokenizer.tokenize(word)
                term_tokens.append(stemmed[0] if stemmed else word.lower())

        if not self._is_well_formed(term_tokens):
            print(f"Malformed boolean query: {query}")
            return []

        # Step 3: get all docs for NOT operations

        all_docs = self.index.all_doc_ids

        if not all_docs:
            print("Index is empty")
            return []

        original_length = len(term_tokens)
        pos = 0

        try:
            while pos < len(term_tokens):
                word = term_tokens[pos]

                # single term
                if original_length == 1:
                    doc_ids = self._resolve_term(word)
                    term_tokens[pos] = doc_ids
                    break

                if word in boolean_terms:
                    if word == "NOT":
                        list2 = self._resolve_term(term_tokens[pos + 1])
                        negated = all_docs.difference(list2)
                        term_tokens[pos] = negated
                        term_tokens.pop(pos + 1)
                        pos = 0
                        continue

                    if word in {"AND", "OR"} and pos + 2 < len(term_tokens) and term_tokens[pos + 1] == "NOT":
                        list1 = self._resolve_term(term_tokens[pos - 1])
                        list2 = self._resolve_term(term_tokens[pos + 2])
                        negated = all_docs.difference(list2)

                        if word == "AND":
                            result = list1.intersection(negated)
                        else:
                            result = list1.union(negated)

                        term_tokens[pos] = result
                        term_tokens.pop(pos + 2)
                        term_tokens.pop(pos + 1)
                        term_tokens.pop(pos - 1)
                        pos = 0
                        continue

                    list1 = self._resolve_term(term_tokens[pos - 1])
                    list2 = self._resolve_term(term_tokens[pos + 1])

                    if word == "AND":
                        term_tokens[pos] = list1.intersection(list2)
                    elif word == "OR":
                        term_tokens[pos] = list1.union(list2)

                    term_tokens.pop(pos + 1)
                    term_tokens.pop(pos - 1)
                    pos = 0
                    continue

                pos += 1

        except Exception as e:
            print(f"Boolean resolution failed: {e}")
            return []

        # Step 4: extract final doc_id set
        if not term_tokens:
            return []

        final = term_tokens[0]
        if isinstance(final, str):
            result_ids = self._resolve_term(final)
        elif isinstance(final, set):
            result_ids = final
        else:
            return []

        if not result_ids:
            print(f"No documents matched: {query}")
            return []

        # Step 5: fetch documents
        candidates = []
        for doc_id in result_ids:
            doc = self.repository.get(doc_id)
            if doc:
                candidates.append(doc)

        if not candidates:
            return []

        # Step 6: rank with existing ranker
        query_terms = [
            t for t in term_tokens
            if isinstance(t, str) and t not in boolean_terms
        ]
        if not query_terms:
            query_terms = self.tokenizer.tokenize(
                re.sub(r'\b(AND|OR|NOT)\b', '', query)
            )

        if not query_terms:
            return []

        ranked = self.ranker.rank(query_terms, candidates, self.index)
        return ranked[:top_k]

    def cascade_search(self, query, weights=None, max_results=25, isSpanish: bool = False) -> list[dict]:
        """
        Unified search combining exact match, ordered matches, TF-IDF, coverage, phoneme and popularity.
        Priority: exact match → ordered match → TF-IDF → term coverage → phoneme → popularity
        """

        T = {}
        t = time.perf_counter()

        # Step 1: tokenize
        if isSpanish:
            query_terms = self.tokenizer.tokenize(query, for_spanish=True)
        else:
            query_terms = self.tokenizer.tokenize(query)
        T['1_tokenize'] = (time.perf_counter() - t) * 1000; t = time.perf_counter()
        print ("Tokenized querry")
        print (query_terms)


        total_query_terms = len(query_terms)
        if total_query_terms == 0:
            return []

        # Default weights
        if weights is None:
            weights = {
                'ordered_match': 0.15,
                'tfidf_score':   0.10,
                'bm25_score':    0.10,
                'term_coverage': 0.15,
                'phoneme':       0.45,
                'popularity':    0.05,
            }

        # Step 2: phoneme search (runs first so results can guide candidate selection)
        try:
            start_time = time.perf_counter()
            phoneme_results = self.search_phonemes(query, top_k=200)
            phoneme_lookup = {doc_id: score for doc_id, score, window_start in phoneme_results}

            max_phoneme = max(phoneme_lookup.values()) if phoneme_lookup else 1.0
            if max_phoneme == 0:
                max_phoneme = 1.0
            print(f"  [T] phoneme search: {len(phoneme_results)} docs in {(time.perf_counter() - start_time)*1000:.1f}ms")
            print(f"  [T] max_phoneme: {max_phoneme}")
        except Exception as e:
            print(f"  [T] phoneme search failed: {e}")
            phoneme_lookup = {}
            max_phoneme = 1.0
        T['2_phoneme'] = (time.perf_counter() - t) * 1000; t = time.perf_counter()
        debug.dprint(f"  [T] phoneme: {T['2_phoneme']:.1f}ms", level=1)

        # Deduplicate query terms
        all_query_terms = list(dict.fromkeys(query_terms))

        # Load doc_id sets (cheap blobs) for rare terms only
        MAX_DF_RATIO = 0.05
        max_df = int(self.index.doc_count * MAX_DF_RATIO)

        doc_id_sets = self.index.get_doc_ids_bulk(all_query_terms)

        rare_terms = []
        common_terms = []
        for term in all_query_terms:
            df = len(doc_id_sets.get(term, set()))
            if df <= max_df:
                rare_terms.append(term)
            else:
                common_terms.append(term)
                debug.dprint(f"  [T] common term '{term}' (df={df:,}, max={max_df:,})", level=1)

        if not rare_terms:
            rarest = min(all_query_terms, key=lambda t: len(doc_id_sets.get(t, set())))
            rare_terms = [rarest]
            debug.dprint(f"  [T] kept rarest term '{rarest}'", level=1)

        debug.dprint(f"  [T] rare: {rare_terms}, common: {common_terms}", level=1)

        # Candidate selection using RARE terms only
        target_candidates = 1000 if len(rare_terms) >= 2 else 2000
        candidate_ids = set()
        n = len(rare_terms)
        min_matches = max(1, 3 * n // 4)

        doc_match_count = {}
        for term in rare_terms:
            if term in doc_id_sets:
                for doc_id in doc_id_sets[term]:
                    doc_match_count[doc_id] = doc_match_count.get(doc_id, 0) + 1
        doc_match_count = {doc_id: count for doc_id, count in doc_match_count.items() if count >= min_matches}

        T['3_candidate_ids_bulk'] = (time.perf_counter() - t) * 1000; t = time.perf_counter()
        debug.dprint(f"  [T] candidate_ids_bulk: {T['3_candidate_ids_bulk']:.1f}ms | {len(doc_match_count)} docs above min_matches", level=1)




        if phoneme_lookup and doc_match_count:
            sample_phoneme_key = next(iter(phoneme_lookup))
            sample_tier_key = next(iter(doc_match_count))
            debug.dprint(f"  [T] phoneme_lookup key type: {type(sample_phoneme_key)} example: {sample_phoneme_key}", level=2)
            debug.dprint(f"  [T] doc_match_count key type: {type(sample_tier_key)} example: {sample_tier_key}", level=2)
        first_tier = True
        for threshold in range(n, min_matches - 1, -1):
            tier = {doc_id for doc_id, count in doc_match_count.items() if count == threshold}

            if first_tier:
                if len(tier) == 0:
                    continue
                first_tier = False
                if len(tier) <= target_candidates:
                    candidate_ids |= tier
                    debug.dprint(f"  [T] threshold {threshold}: {len(tier)} docs, total {len(candidate_ids)} (full tier)", level=2)
                else:
                    # always include docs matching ALL known terms (only useful with 2+ terms)
                    # known_terms = [kt for kt in query_terms if kt in posting_lists]
                    # if len(known_terms) >= 2:
                    #     exact_known = set(posting_lists[known_terms[0]].doc_ids())
                    #     for kt in known_terms[1:]:
                    #         exact_known &= posting_lists[kt].doc_ids()
                    #     candidate_ids |= exact_known
                    #     debug.dprint(f"  [T] added {len(exact_known)} docs matching all known terms", level=2)
                    if n >= 2:
                        exact_known = {doc_id for doc_id, count in doc_match_count.items() if count == n}
                        candidate_ids |= exact_known
                        debug.dprint(f"  [T] added {len(exact_known)} docs matching all terms", level=2)
                    # add phoneme matches from tier
                    phoneme_in_tier = tier & set(phoneme_lookup.keys())
                    candidate_ids |= phoneme_in_tier
                    debug.dprint(f"  [T] threshold {threshold}: tier too big ({len(tier)}), phoneme matches: {len(phoneme_in_tier)}", level=2)

                    # fill remainder sorted by phoneme score
                    if len(candidate_ids) < target_candidates:
                        remaining = tier - candidate_ids
                        needed = target_candidates - len(candidate_ids)
                        sorted_remaining = sorted(
                            remaining,
                            key=lambda d: phoneme_lookup.get(d, 0.0),
                            reverse=True
                        )
                        candidate_ids |= set(sorted_remaining[:needed])
                        debug.dprint(f"  [T] filled to {len(candidate_ids)} candidates", level=2)

                if len(candidate_ids) >= target_candidates:
                    break
            else:
                if len(candidate_ids) + len(tier) > target_candidates * 2:
                    break
                candidate_ids |= tier
                debug.dprint(f"  [T] threshold {threshold}: {len(tier)} docs, total {len(candidate_ids)}", level=2)
                if len(candidate_ids) >= target_candidates:
                    break

        # fallback to phoneme candidates if no term matches
        if len(candidate_ids) == 0 and phoneme_lookup:
            candidate_ids = set(phoneme_lookup.keys())
            debug.dprint(f"  [T] no term candidates, using {len(candidate_ids)} phoneme candidates", level=1)

        # T['4_candidate_selection'] = (time.perf_counter() - t) * 1000; t = time.perf_counter()
        # for term in posting_lists:
        #     posting_lists[term] = posting_lists[term].filter(candidate_ids)
        # debug.dprint(f"  [T] candidate_selection: {T['4_candidate_selection']:.1f}ms | {len(candidate_ids):,} candidates", level=1)

        T['4_candidate_selection'] = (time.perf_counter() - t) * 1000; t = time.perf_counter()
        debug.dprint(f"  [T] candidate_selection: {T['4_candidate_selection']:.1f}ms | {len(candidate_ids):,} candidates", level=1)

        # load full posting lists for ALL terms, filtered to candidates
        posting_lists = self.index.get_posting_lists_bulk(all_query_terms)
        for term in posting_lists:
            posting_lists[term] = posting_lists[term].filter(candidate_ids)
        T['4_bulk_load_filtered'] = (time.perf_counter() - t) * 1000; t = time.perf_counter()
        debug.dprint(f"  [T] bulk_load_filtered: {T['4_bulk_load_filtered']:.1f}ms", level=1)

        # Use ALL terms for scoring
        query_terms = all_query_terms

        # # Step 4: batch fetch
        LightDoc = namedtuple('LightDoc', ['id', 'views'])
        candidate_docs = [LightDoc(id=row[0], views=row[1])
                          for row in self.repository.get_many_lightweight(list(candidate_ids))]
        T['4_fetch_docs'] = (time.perf_counter() - t) * 1000; t = time.perf_counter()
        debug.dprint(f"  [T] fetch_docs: {T['4_fetch_docs']:.1f}ms | {len(candidate_docs):,} docs", level=1)

        # Step 4: tfidf
        tfidf_lookup, max_tfidf = self.ranker.score_documents(query_terms, candidate_docs, self.index, posting_lists=posting_lists)
        T['4_tfidf'] = (time.perf_counter() - t) * 1000; t = time.perf_counter()
        debug.dprint(f"  [T] tfidf: {T['4_tfidf']:.1f}ms", level=1)

        # Step 5: bm25
        bm25_lookup, max_bm25 = BM25Ranking().score_documents(query_terms, candidate_docs, self.index, posting_lists=posting_lists)
        T['5_bm25'] = (time.perf_counter() - t) * 1000; t = time.perf_counter()
        debug.dprint(f"  [T] bm25: {T['5_bm25']:.1f}ms", level=1)


        # Step 7: popularity
        views_lookup = {doc.id: (doc.views or 0) for doc in candidate_docs}
        max_views = max(views_lookup.values()) if views_lookup else 1
        if max_views == 0:
            max_views = 1
        T['7_popularity'] = (time.perf_counter() - t) * 1000; t = time.perf_counter()

        # Step 8: proximity
        if len(query_terms) >= 2:
            proximity_results = self._resolve_partial_matches(query_terms, max_results=max_results*20, posting_lists=posting_lists, candidate_ids=candidate_ids)
        else:
            proximity_results = []
        T['8_proximity_resolve'] = (time.perf_counter() - t) * 1000; t = time.perf_counter()
        debug.dprint(f"  [T] proximity_resolve: {T['8_proximity_resolve']:.1f}ms", level=1)

        proximity_lookup = self.proximity_ranker.score_documents(query_terms, proximity_results)
        T['9_proximity_score'] = (time.perf_counter() - t) * 1000; t = time.perf_counter()
        debug.dprint(f"  [T] proximity_score: {T['9_proximity_score']:.1f}ms", level=1)

        # Step 9: merge and score
        all_docs = set(tfidf_lookup.keys()) | set(proximity_lookup.keys())
        if not all_docs:
            return []

        def score_document(doc_id):
            if doc_id in tfidf_lookup:
                tfidf_data = tfidf_lookup[doc_id]
                norm_tfidf = tfidf_data['total_score'] / max_tfidf
                norm_bm25 = bm25_lookup[doc_id]['total_score'] / max_bm25 if doc_id in bm25_lookup else 0.0
                term_positions = tfidf_data['term_positions']
                term_scores = tfidf_data['term_scores']
            else:
                norm_tfidf = 0.0
                norm_bm25 = 0.0
                term_positions = {term: [] for term in query_terms}
                term_scores = {}

            if doc_id in proximity_lookup:
                norm_exact           = proximity_lookup[doc_id]['norm_exact']
                norm_ordered         = proximity_lookup[doc_id]['norm_ordered']
                norm_coverage        = proximity_lookup[doc_id]['norm_coverage']
                start_position       = proximity_lookup[doc_id]['start_position']
                ordered_term_indices = proximity_lookup[doc_id]['ordered_term_indices']
            else:
                norm_exact           = 0.0
                norm_ordered         = 0.0
                norm_coverage        = 0.0
                start_position       = None
                ordered_term_indices = []


            # phoneme_tuple = phoneme_lookup.get(doc_id)
            # if phoneme_tuple:
            #     norm_phoneme    = phoneme_tuple[0] / max_phoneme if max_phoneme > 0 else 0.0
            #     start_position  = phoneme_tuple[1]
            # else:
            #     norm_phoneme    = 0.0
            #     start_position  = None
            # norm_popularity = views_lookup.get(doc_id, 0) / max_views if max_views > 0 else 0.0
            norm_phoneme    = phoneme_lookup.get(doc_id, 0.0) / max_phoneme
            norm_popularity = views_lookup.get(doc_id, 0) / max_views


            combined_score = (
                    weights.get('ordered_match', 0) * norm_ordered +
                    weights.get('tfidf_score', 0)   * norm_tfidf +
                    weights.get('bm25_score', 0)    * norm_bm25 +
                    weights.get('term_coverage', 0) * norm_coverage +
                    weights.get('phoneme', 0)       * norm_phoneme +
                    weights.get('popularity', 0)    * norm_popularity
            )

            return {
                'doc_id': doc_id,
                'combined_score': combined_score,
                'term_positions': term_positions,
                'term_scores': term_scores,
                'snippet_start_position': start_position,
                'ordered_term_indices': ordered_term_indices,
                'breakdown': {
                    'norm_exact': norm_exact,
                    'norm_ordered': norm_ordered,
                    'norm_tfidf': norm_tfidf,
                    'norm_bm25': norm_bm25,
                    'norm_coverage': norm_coverage,
                    'norm_phoneme': norm_phoneme,
                    'norm_popularity': norm_popularity,
                }
            }

        scored_results = [score_document(doc_id) for doc_id in all_docs]
        T['10_scoring'] = (time.perf_counter() - t) * 1000; t = time.perf_counter()
        debug.dprint(f"  [T] scoring: {T['10_scoring']:.1f}ms", level=1)
        debug_sorted = sorted(scored_results, key=lambda x: x['combined_score'], reverse=True)
        for r in debug_sorted[:10]:
            b = r['breakdown']
            debug.dprint(
                f"  [SCORE] {r['doc_id']}: {r['combined_score']:.4f} | "
                f"ordered={b['norm_ordered']:.3f} tfidf={b['norm_tfidf']:.3f} "
                f"bm25={b['norm_bm25']:.3f} coverage={b['norm_coverage']:.3f} "
                f"phoneme={b['norm_phoneme']:.3f} popularity={b['norm_popularity']:.3f}",
                level=1
            )


        exact_matches = [r for r in scored_results if r['breakdown']['norm_exact'] > 0 or r['breakdown']['norm_ordered'] == 1.0]
        non_exact     = [r for r in scored_results if r['breakdown']['norm_exact'] == 0 and r['breakdown']['norm_ordered'] < 1.0]
        exact_matches.sort(key=lambda x: x['combined_score'], reverse=True)
        non_exact.sort(key=lambda x: x['combined_score'], reverse=True)

        debug.dprint(f"  [T] TOTAL: {sum(T.values()):.1f}ms", level=1)
        return (exact_matches + non_exact)[:max_results]


    def cascade_results_to_tuples(self, results, query_terms, top_n=10) -> list[tuple]:
        """
        Convert cascade_search results to (doc_id, position) tuples.
        Improved Waterfall: Exact/Phonetic -> Ordered Sequence -> Best TF-IDF -> Fallback
        """
        tuple_list = []

        for result in results[:top_n]:
            doc_id = result['doc_id']
            term_positions = result.get('term_positions', {})
            term_scores = result.get('term_scores', {})
            breakdown = result.get('breakdown', {})
            snippet_start = result.get('snippet_start_position')
            
            position = None
            priority_label = "none"

            # 1. High-Confidence Anchor (Exact or Phonetic)
            # We group these because the engine has already found a specific window
            if snippet_start is not None:
                if breakdown.get('norm_exact', 0) == 1.0:
                    position = snippet_start
                    priority_label = "exact"
                elif breakdown.get('norm_phoneme', 0) > 0:
                    position = snippet_start
                    priority_label = "phoneme"

            # 2. Sequence Anchor (Ordered match)
            if position is None and breakdown.get('norm_ordered', 0) > 0:
                ordered_indices = result.get('ordered_term_indices', [])
                for idx in ordered_indices:
                    if idx < len(query_terms):
                        term = query_terms[idx]
                        positions = term_positions.get(term)
                        if positions:
                            # Use engine's suggested start if available, else first term position
                            position = snippet_start if snippet_start is not None else min(positions)
                            priority_label = "ordered"
                            break

            # 3. Statistical Anchor (Highest TF-IDF)
            if position is None and term_scores:
                # Sort terms by score descending to find the 'heaviest' term present in doc
                sorted_terms = sorted(term_scores.items(), key=lambda x: x[1], reverse=True)
                for term, score in sorted_terms:
                    positions = term_positions.get(term)
                    if positions:
                        # Filter for valid positions > 0 if possible
                        valid_pos = [p for p in positions if p >= 0]
                        if valid_pos:
                            position = min(valid_pos)
                            priority_label = "tfidf"
                            break

            # 4. Emergency Fallback (First available term)
            if position is None:
                for term in query_terms:
                    positions = term_positions.get(term)
                    if positions:
                        position = positions[0]
                        priority_label = "fallback"
                        break

            debug.dprint(
                f"[DEBUG] doc:{doc_id} position:{position} priority used: {priority_label} "
                f"{'exact' if breakdown['norm_exact']==1.0 else 'ordered' if breakdown['norm_ordered']>0 else 'tfidf/fallback'}",
                level=2
            )
            debug.dprint(f"[DEBUG] term_positions for {doc_id}: {term_positions}", level=3)

            print(f"[DEBUG] doc:{doc_id} pos:{position} via:{priority_label}")
            tuple_list.append((doc_id, position))

        return tuple_list


#-----------------------phonemes stuff ---------------#


    CMU = cmudict.dict()

    PHONEMES = [
        "AA","AE","AH","AO","AW","AY","B","CH","D","DH","EH","ER","EY",
        "F","G","HH","IH","IY","JH","K","L","M","N","NG","OW","OY","P",
        "R","S","SH","T","TH","UH","UW","V","W","Y","Z","ZH"
    ]
    PHONEME_TO_ID = {p: i for i, p in enumerate(PHONEMES)}
    ID_TO_PHONEME = {i: p for i, p in enumerate(PHONEMES)}




    def tokenize(self, text):
        return re.findall(r"[a-zA-Z']+", text.lower())

    def word_to_phonemes(self, word, CMU):
        if word not in CMU:
            return []
        return [p.rstrip("012") for p in CMU[word][0]]

    def text_to_phoneme_ints(self, text, CMU):
        PHONEMES = [
            "AA","AE","AH","AO","AW","AY","B","CH","D","DH","EH","ER","EY",
            "F","G","HH","IH","IY","JH","K","L","M","N","NG","OW","OY","P",
            "R","S","SH","T","TH","UH","UW","V","W","Y","Z","ZH"
        ]
        PHONEME_TO_ID = {p: i for i, p in enumerate(PHONEMES)}
        words = self.tokenizer.tokenize(text,use_normalize=True, for_spanish=False,use_stemming=False, use_stopping=False)
        print(f"Tokenized query into words: {words}")
        phonemes = []
        for w in words:
            p = self.word_to_phonemes(w, CMU)
            phonemes.extend(p)
        phoneme_ints = [PHONEME_TO_ID[p] for p in phonemes if p in PHONEME_TO_ID]
        return phonemes, phoneme_ints

    def generate_trigrams(self, phoneme_ints):
        return [
            phoneme_ints[i]*1600 + phoneme_ints[i+1]*40 + phoneme_ints[i+2]
            for i in range(len(phoneme_ints)-2)
        ]

    # -----------------------------
    # Fuzzy scoring
    # -----------------------------
    def fuzzy_similarity(self, song_seq, query_seq, doc_id=None):
        best_score = 0
        window_size = len(query_seq)

        if window_size == 0 or len(song_seq) < window_size:
            return 0.0, [], -1

        query_str = "".join(chr(p) for p in query_seq)
        song_str = "".join(chr(p) for p in song_seq)

        step = max(1, window_size // 4)  # 25% stride

        best_index = 0

        # ---- Coarse scan ----
        for i in range(0, len(song_seq) - window_size + 1, step):
            subseq_str = song_str[i:i+window_size]
            distance = Levenshtein.distance(query_str, subseq_str)
            similarity = 1 - distance / window_size

            if similarity > best_score:
                best_score = similarity
                best_index = i

        # ---- Refinement around best window ----
        refine_start = max(0, best_index - step)
        refine_end = min(len(song_seq) - window_size + 1, best_index + step)

        best_score = 0
        best_index = None

        for i in range(refine_start, refine_end):
            subseq_str = song_str[i:i+window_size]
            distance = Levenshtein.distance(query_str, subseq_str)
            similarity = 1 - distance / window_size

            if similarity > best_score:
                best_score = similarity
                best_index = i

        best_window = song_seq[best_index:best_index+window_size] if best_index is not None else []

        word_position = self.get_phoneme_position(doc_id, best_index) if doc_id else None

        return best_score, best_window, word_position

    def phoneme_similarity(self, p1, p2):
        SIMILAR_GROUPS = [
            {"P", "B"},
            {"T", "D"},
            {"K", "G"},
            {"F", "V"},
            {"S", "Z"},
            {"SH", "ZH"},
            {"CH", "JH"},
            {"M", "N", "NG"},
        ]

        VOWELS = {
            "AA", "AE", "AH", "AO", "AW", "AY",
            "EH", "ER", "EY",
            "IH", "IY",
            "OW", "OY",
            "UH", "UW"
        }
        if p1 == p2:
            return 1.0

        # Similar consonant groups
        for group in SIMILAR_GROUPS:
            if p1 in group and p2 in group:
                return 0.8

        # Both vowels (but different)
        if p1 in VOWELS and p2 in VOWELS:
            return 0.6

        # Both consonants (but unrelated)
        if p1 not in VOWELS and p2 not in VOWELS:
            return 0.4

        # Vowel vs consonant
        return 0.0

    def improved_similarity(self, best_window, query_seq, id_to_phoneme = ID_TO_PHONEME):
        """
        Compute similarity allowing substitutions, insertions, and deletions.

        best_window: list[int]  (aligned phoneme IDs from song)
        query_seq:   list[int]  (query phoneme IDs)
        id_to_phoneme: dict[int -> str]

        Returns: normalized similarity [0,1]
        """
        if not best_window or not query_seq:
            return 0.0

        m = len(best_window)
        n = len(query_seq)

        # Initialize DP table
        dp = [[0.0] * (n + 1) for _ in range(m + 1)]

        # Initialize first row/column (cost of insertions/deletions)
        for i in range(1, m + 1):
            dp[i][0] = dp[i-1][0] + 1.0  # deletion
        for j in range(1, n + 1):
            dp[0][j] = dp[0][j-1] + 1.0  # insertion

        # Fill DP table
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                ph_song = id_to_phoneme[best_window[i-1]]
                ph_query = id_to_phoneme[query_seq[j-1]]
                sub_cost = 1.0 - self.phoneme_similarity(ph_song, ph_query)  # 0 if identical

                dp[i][j] = min(
                    dp[i-1][j-1] + sub_cost,  # substitution
                    dp[i-1][j] + 1.0,         # deletion
                    dp[i][j-1] + 1.0          # insertion
                )

        # Normalize: similarity = 1 - (edit distance / max length)
        edit_distance = dp[m][n]
        max_len = max(m, n)

        return max(0.0, 1.0 - edit_distance / max_len if max_len > 0 else 0.0)
    
    def get_phoneme_position(self, doc_id, position):
        """Given a phoneme position in the song's phoneme sequence, return the corresponding word position in the lyrics."""
        song_lyrics_list = self.repository.get(doc_id).content
        words = re.findall(r"[a-zA-Z']+", song_lyrics_list.lower())
        counter = 0
        for i, word in enumerate(words):
            word_phonemes = self.word_to_phonemes(word, self.CMU)
            for phone in word_phonemes:
                if counter == position:
                    return i
                counter += 1
        return -1 # default to start if position exceeds length (Flag to show it's broken)

    def search_phonemes(self, query: str, top_k: int = 10 ):
    
        """
        Returns top_k songs as (doc_id, similarity_score).
        Now queries the DB directly instead of using in-memory global caches.
        """
        CMU = cmudict.dict()
        start_time = time.perf_counter()
        time_t = time.perf_counter()

        _, query_ints = self.text_to_phoneme_ints(query, CMU)
        if not query_ints:
            return []
        debug.dprint(f"  [PHONEME] text_to_phoneme_ints: {(time.perf_counter() - time_t)*1000:.1f}ms", level=2)
        debug.dprint(f"  [PHONEME] query_ints: {query_ints}", level=3)

        t = time.perf_counter()
        query_trigrams = self.generate_trigrams(query_ints)
        num_trigrams = len(query_trigrams)
        debug.dprint(f"  [PHONEME] generate_trigrams: {(time.perf_counter() - t)*1000:.1f}ms | {num_trigrams} trigrams", level=2)

        # 2. Determine threshold
        if num_trigrams <= 8:
            overlap_ratio = 0.3
        elif num_trigrams <= 20:
            overlap_ratio = 0.2
        elif num_trigrams <= 40:
            overlap_ratio = 0.2
        else:
            overlap_ratio = 0.2
        threshold = max(2, int(num_trigrams * overlap_ratio))
        debug.dprint(f"  [PHONEME] threshold: {threshold} (ratio={overlap_ratio}, trigrams={num_trigrams})", level=2)

        # 3. Candidate filtering via Database
        t = time.perf_counter()
        candidate_query = self.index.get_trigrams(threshold, query_trigrams)
        candidates = [row.document_id for row in candidate_query]
        debug.dprint(f"  [PHONEME] get_trigrams: {(time.perf_counter() - t)*1000:.1f}ms | {len(candidates)} candidates", level=1)

        if not candidates:
            debug.dprint("  [PHONEME] no candidates passed trigram filter", level=1)
            return []

        # 4. Fetch Phoneme Sequences
        t = time.perf_counter()
        phoneme_data = self.index.get_phoneme_data(candidates)
        candidate_sequences = {row.document_id: list(row.phonemes) for row in phoneme_data}
        debug.dprint(f"  [PHONEME] get_phoneme_data: {(time.perf_counter() - t)*1000:.1f}ms | {len(candidate_sequences)} sequences", level=1)

        # 5. Fuzzy scoring
        t = time.perf_counter()
        results = []
        for doc_id in candidates:
            seq = candidate_sequences.get(doc_id)
            if not seq:
                continue
            
            score, best_window, word_position = self.fuzzy_similarity(seq, query_ints, doc_id)
            
            if score > 0:
                results.append({
                    "doc_id": doc_id,
                    "score": score,
                    "best_window": best_window,
                    "word_position": word_position
                })
        debug.dprint(f"  [PHONEME] fuzzy_scoring: {(time.perf_counter() - t)*1000:.1f}ms | {len(results)} scored", level=1)

        # 6. Improved similarity refinement
        t = time.perf_counter()
        results.sort(key=lambda x: x['score'], reverse=True)

        final_results = []
        for i in range(min(top_k * 2, len(results))):
            item = results[i]
            doc_id = item['doc_id']
            score = item['score']
            best_window = item['best_window']
            word_position = item['word_position']

            if best_window:
                best_score = self.improved_similarity(best_window, query_ints)
            else:
                best_score = score

            final_results.append((doc_id, best_score, word_position))

        final_results.sort(key=lambda x: x[1], reverse=True)
        print(f"Refined top candidates in {(time.perf_counter() - t)*1000:.1f}ms")
        print(f"Total search time: {(time.perf_counter() - start_time)*1000:.1f}ms")

        for doc_id, score, word_position in final_results[:20]:
            debug.dprint(f"Doc ID: {doc_id}, Final Phoneme Similarity Score: {score:.4f}, Word Position: {word_position} \n Doc name: {self.repository.get(doc_id).title if self.repository.get(doc_id) else 'Unknown'}", level=2)

        return final_results[:top_k]