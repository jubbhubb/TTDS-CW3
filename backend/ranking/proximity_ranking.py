
from ranking.proximity_helpers import min_ordered_distance, find_ordered_terms


class ProximityRanking:

    def score_documents(self, query_terms, proximity_results, debug=False) -> dict:
        """
        Builds proximity lookup with normalised signals per document.

        Returns:
            {doc_id: {
                'norm_exact': float,           # 1.0 if exact match, 0.0 otherwise
                'norm_ordered': float,         # ordered_length / total_query_terms
                'norm_coverage': float,        # terms_present / total_query_terms
                'start_position': int,         # for snippet extraction
                'ordered_term_indices': list,  # for snippet extraction
            }}
        """
        total_query_terms = len(query_terms)
        proximity_lookup = {}

        for tier_index, (doc_set, pos_dict) in enumerate(proximity_results):
            terms_in_sequence = total_query_terms - tier_index

            for doc_id in doc_set:
                positions = pos_dict[doc_id]

                prox_result = min_ordered_distance(positions)

                if prox_result[0] is None:
                    min_dist = None
                    start_pos = None
                    is_ordered = False
                    ordered_term_indices = []
                else:
                    min_dist, start_pos = prox_result
                    is_ordered = True
                    ordered_term_indices = find_ordered_terms(positions, query_terms)

                terms_present = sum(1 for pos_list in positions if pos_list)
                ordered_length = len(ordered_term_indices)

                is_exact = (
                        is_ordered and
                        terms_in_sequence == total_query_terms and
                        min_dist == total_query_terms - 1
                )

                # normalise
                norm_exact = 1.0 if is_exact else 0.0
                norm_ordered = (ordered_length / total_query_terms
                                if is_ordered and not is_exact else 0.0)
                norm_coverage = terms_present / total_query_terms

                if doc_id not in proximity_lookup:
                    result = {
                        'norm_exact': norm_exact,
                        'norm_ordered': norm_ordered,
                        'norm_coverage': norm_coverage,
                        'start_position': start_pos,
                        'ordered_term_indices': ordered_term_indices,
                    }

                    if debug:
                        result.update({
                            'is_exact': is_exact,
                            'is_ordered': is_ordered,
                            'terms_present': terms_present,
                            'ordered_length': ordered_length,
                        })

                    proximity_lookup[doc_id] = result

        return proximity_lookup