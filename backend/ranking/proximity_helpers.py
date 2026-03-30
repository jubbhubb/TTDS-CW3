# ranking/proximity_utils.py

def min_ordered_distance(position_lists, max_dist=30):  # remove self
    lists = [sorted(lst) for lst in position_lists if lst]
    k = len(lists)

    if k < 2:
        return None, None

    dp = [[] for _ in range(k)]
    dp[0] = lists[0][:]

    for i in range(1, k):
        prev_positions = lists[i - 1]
        prev_dp = dp[i - 1]
        curr_positions = lists[i]

        curr_dp = []
        best_start = float('inf')
        p = 0

        for pos in curr_positions:
            while p < len(prev_positions) and prev_positions[p] < pos:
                best_start = min(best_start, prev_dp[p])
                p += 1
            curr_dp.append(best_start)

        dp[i] = curr_dp

    min_dist = float('inf')
    best_start_pos = None

    for start, end in zip(dp[-1], lists[-1]):
        if start < float('inf'):
            dist = end - start
            if dist < min_dist:
                min_dist = dist
                best_start_pos = start

    if min_dist < max_dist:
        return min_dist, best_start_pos
    else:
        return None, None


def find_ordered_terms(positions, query_terms):  # remove self
    terms_with_positions = [(i, pos) for i, pos in enumerate(positions) if pos]

    if len(terms_with_positions) < 2:
        return [i for i, _ in terms_with_positions]

    best_sequence = []

    for start_idx, (term_idx, term_positions) in enumerate(terms_with_positions):
        for start_pos in term_positions:
            current_sequence = [term_idx]
            current_pos = start_pos

            for next_idx in range(start_idx + 1, len(terms_with_positions)):
                next_term_idx, next_positions = terms_with_positions[next_idx]
                valid_positions = [p for p in next_positions if p > current_pos]
                if valid_positions:
                    current_sequence.append(next_term_idx)
                    current_pos = min(valid_positions)

            if len(current_sequence) > len(best_sequence):
                best_sequence = current_sequence

    return best_sequence