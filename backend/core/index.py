import os
import pickle
import sqlite3
from collections import defaultdict
import array
import time

class PostingEntry:
    __slots__ = ("doc_id", "positions")

    def __init__(self, doc_id: str, positions):
        self.doc_id = doc_id
        if isinstance(positions, array.array):
            self.positions = positions
        else:
            self.positions = array.array('I', positions)

    @property
    def term_frequency(self) -> int:
        return len(self.positions)

    def __repr__(self) -> str:
        return f"PostingEntry({self.doc_id}, positions={list(self.positions)})"

class PostingList:
    """A list of PostingEntries for a single term, with fast doc lookup."""

    def __init__(self):
        self._entries: dict[str, PostingEntry] = {}

    def add(self, doc_id: str, positions: list[int]) -> None:
        if doc_id in self._entries:
            self._entries[doc_id].positions.extend(positions)
        else:
            self._entries[doc_id] = PostingEntry(doc_id, positions)

    def get(self, doc_id: str) -> PostingEntry | None:
        return self._entries.get(doc_id)

    def doc_ids(self) -> set[str]:
        return set(self._entries.keys())

    def doc_frequency(self) -> int:
        return len(self._entries)

    def filter(self, doc_ids: set) -> 'PostingList':
        filtered = PostingList()
        for doc_id in doc_ids:
            entry = self._entries.get(doc_id)
            if entry:
                deduped = PostingEntry(entry.doc_id, sorted(set(entry.positions)))
                filtered._entries[doc_id] = deduped
        return filtered

    def __iter__(self):
        return iter(self._entries.values())

    def __len__(self) -> int:
        return len(self._entries)


class PositionalIndex:
    def __init__(self, tokenizer=None, index_dir=None):
        self.tokenizer = tokenizer
        self.index_dir = index_dir
        self._doc_lengths: dict[str, int] = {}
        self._doc_count = 0
        self._use_sqlite = False
        self._conn = None
        self._posting_cache = {}

        if index_dir:
            os.makedirs(index_dir, exist_ok=True)
            self._db_path = os.path.join(index_dir, "index.db") #this is the path you get from engine generation
            self._conn = sqlite3.connect(self._db_path)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA cache_size=-64000")
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS postings (
                    term TEXT PRIMARY KEY,
                    data BLOB
                )
            """)
            self._conn.commit()
            self._index = None
            self._use_sqlite = True
            print(f"  📀 Disk-backed index at {os.path.abspath(self._db_path)}")
        else:
            self._index = defaultdict(PostingList)
            print(f"  🧠 In-memory index")

    def add_document(self, doc_id: str, tokens: list[str]) -> None:
        self._doc_count += 1
        self._doc_lengths[doc_id] = len(tokens)

        term_positions: dict[str, list[int]] = defaultdict(list)
        for position, token in enumerate(tokens):
            term_positions[token].append(position)

        # always build in memory — flush_chunk handles SQLite writes
        if not hasattr(self, '_chunk_index'):
            self._chunk_index: dict[str, PostingList] = {}

        for term, positions in term_positions.items():
            if term not in self._chunk_index:
                self._chunk_index[term] = PostingList()
            self._chunk_index[term].add(doc_id, positions)

        if not self._use_sqlite:
            # in-memory mode — merge directly into _index
            for term, pl in self._chunk_index.items():
                for entry in pl:
                    self._index[term].add(entry.doc_id, entry.positions)
            self._chunk_index = {}

    def flush_chunk(self) -> None:
        if not self._use_sqlite or not hasattr(self, '_chunk_index') or not self._chunk_index:
            return

        terms = list(self._chunk_index.keys())
        existing = {}

        # fetch in batches of 999 due to SQLite variable limit
        for i in range(0, len(terms), 999):
            batch_terms = terms[i:i+999]
            placeholders = ','.join('?' * len(batch_terms))
            rows = self._conn.execute(
                f"SELECT term, data FROM postings WHERE term IN ({placeholders})", batch_terms
            ).fetchall()
            for row in rows:
                existing[row[0]] = pickle.loads(row[1])

        for term, new_pl in self._chunk_index.items():
            if term in existing:
                pl = existing[term]
            else:
                pl = PostingList()
            for entry in new_pl:
                pl.add(entry.doc_id, entry.positions)
            existing[term] = pl

        self._conn.executemany(
            "INSERT OR REPLACE INTO postings (term, data) VALUES (?, ?)",
            [(term, pickle.dumps(pl)) for term, pl in existing.items()]
        )
        self._conn.commit()
        self._chunk_index = {}

    def _get_posting_list_sqlite(self, term: str) -> PostingList | None:
        row = self._conn.execute(
            "SELECT data FROM postings WHERE term=?", (term,)
        ).fetchone()
        if row:
            return pickle.loads(row[0])
        return None
    def get_posting_list(self, term: str) -> PostingList | None:
        if self._use_sqlite:
            return self._get_posting_list_sqlite(term)
        return self._index.get(term)

    def lookup(self, term: str) -> set[str]:
        posting_list = self.get_posting_list(term)
        return posting_list.doc_ids() if posting_list else set()

    def term_frequency(self, term: str, doc_id: str) -> int:
        posting_list = self.get_posting_list(term)
        if not posting_list:
            return 0
        entry = posting_list.get(doc_id)
        return entry.term_frequency if entry else 0

    def term_positions(self, term: str, doc_id: str) -> list[int]:
        posting_list = self.get_posting_list(term)
        if not posting_list:
            return []
        entry = posting_list.get(doc_id)
        return entry.positions if entry else []

    def doc_frequency(self, term: str) -> int:
        posting_list = self.get_posting_list(term)
        return posting_list.doc_frequency() if posting_list else 0

    def doc_length(self, doc_id: str) -> int:
        return self._doc_lengths.get(doc_id, 0)

    @property
    def avg_doc_length(self) -> float:
        if not self._doc_lengths:
            return 0.0
        return sum(self._doc_lengths.values()) / len(self._doc_lengths)

    @property
    def doc_count(self) -> int:
        return self._doc_count

    @property
    def all_doc_ids(self) -> set[str]:
        return set(self._doc_lengths.keys())

    @property
    def num_terms(self) -> int:
        if self._use_sqlite:
            row = self._conn.execute("SELECT COUNT(*) FROM postings").fetchone()
            return row[0] if row else 0
        return len(self._index)

    def phrase_search(self, phrase_tokens: list[str]) -> set[str]:
        if not phrase_tokens:
            return set()

        first_posting = self.get_posting_list(phrase_tokens[0])
        if not first_posting:
            return set()

        candidate_docs = first_posting.doc_ids()

        for token in phrase_tokens[1:]:
            posting = self.get_posting_list(token)
            if not posting:
                return set()
            candidate_docs &= posting.doc_ids()

        matched_docs = set()
        for doc_id in candidate_docs:
            start_positions = self.term_positions(phrase_tokens[0], doc_id)
            for start_pos in start_positions:
                found_phrase = True
                for offset, token in enumerate(phrase_tokens[1:], start=1):
                    positions = self.term_positions(token, doc_id)
                    if (start_pos + offset) not in positions:
                        found_phrase = False
                        break
                if found_phrase:
                    matched_docs.add(doc_id)
                    break

        return matched_docs

    def proximity_score(self, query_tokens: list[str], doc_id: str) -> float:
        token_positions: list[list[int]] = []
        for token in query_tokens:
            positions = self.term_positions(token, doc_id)
            if not positions:
                return 0.0
            token_positions.append(positions)

        if len(token_positions) < 2:
            return 1.0

        min_span = float("inf")
        pointers = [0] * len(token_positions)

        while True:
            current_positions = [
                token_positions[i][pointers[i]] for i in range(len(token_positions))
            ]
            span = max(current_positions) - min(current_positions)
            min_span = min(min_span, span)

            if min_span == len(token_positions) - 1:
                break

            min_idx = current_positions.index(min(current_positions))
            pointers[min_idx] += 1

            if pointers[min_idx] >= len(token_positions[min_idx]):
                break

        if min_span == float("inf"):
            return 0.0

        ideal_span = len(token_positions) - 1
        return ideal_span / max(min_span, ideal_span)

    def save(self, directory: str) -> dict:
        os.makedirs(directory, exist_ok=True)
        lengths_path = os.path.join(directory, "doc_lengths.pkl")
        metadata_path = os.path.join(directory, "metadata.pkl")

        if self._use_sqlite and self._conn:
            self._conn.commit()

        with open(lengths_path, "wb") as f:
            pickle.dump(self._doc_lengths, f)

        metadata = {"doc_count": self._doc_count}
        with open(metadata_path, "wb") as f:
            pickle.dump(metadata, f)

        return {
            "lengths_path": lengths_path,
            "metadata_path": metadata_path,
            "terms": self.num_terms,
            "docs": self._doc_count
        }

    def build_term_docs_table(self):
        self._conn.execute("DROP TABLE IF EXISTS term_docs")
        self._conn.execute("""
        CREATE TABLE term_docs (
            term TEXT,
            doc_id TEXT,
            PRIMARY KEY (term, doc_id)
        )
    """)
        cursor = self._conn.execute("SELECT COUNT(*) FROM postings")
        total = cursor.fetchone()[0]
        print(f"  Migrating {total} terms...")

        cursor = self._conn.execute("SELECT term, data FROM postings")
        batch = []
        count = 0
        for term, data in cursor:
            pl = pickle.loads(data)
            for doc_id in pl.doc_ids():
                batch.append((term, doc_id))
            if len(batch) > 100000:
                self._conn.executemany("INSERT INTO term_docs VALUES (?, ?)", batch)
                count += len(batch)
                print(f"  ... {count:,} rows inserted")
                batch = []
        if batch:
            self._conn.executemany("INSERT INTO term_docs VALUES (?, ?)", batch)
            count += len(batch)

        print(f"  Creating index...")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_term_docs_term ON term_docs(term)")
        self._conn.commit()
        print(f"  Done. {count:,} total rows in term_docs.")


    def warm_cache(self, top_n=50):
        print(f"  [CACHE] Starting warm_cache for top {top_n} terms...")

        # Step 1: find the biggest terms
        print(f"  [CACHE] Querying for largest blobs...")
        t0 = time.perf_counter()
        rows = self._conn.execute(
            "SELECT term, length(data) as size FROM postings ORDER BY size DESC LIMIT ?", (top_n,)
        ).fetchall()
        print(f"  [CACHE] Found {len(rows)} terms in {time.perf_counter() - t0:.1f}s")

        for i, (term, size) in enumerate(rows):
            print(f"  [CACHE] [{i+1}/{len(rows)}] Loading '{term}' ({size/1024/1024:.1f}MB blob)...")

            t1 = time.perf_counter()
            row = self._conn.execute("SELECT data FROM postings WHERE term = ?", (term,)).fetchone()
            t_fetch = time.perf_counter() - t1
            print(f"    fetch: {t_fetch:.1f}s")

            t2 = time.perf_counter()
            pl = pickle.loads(row[0])
            t_unpickle = time.perf_counter() - t2
            print(f"    unpickle: {t_unpickle:.1f}s ({pl.doc_frequency():,} entries)")

            t3 = time.perf_counter()
            for entry in pl:
                entry.positions = array.array('I', entry.positions)
            t_compact = time.perf_counter() - t3
            print(f"    compact: {t_compact:.1f}s")

            self._posting_cache[term] = pl
            print(f"    total: {time.perf_counter() - t1:.1f}s")

        print(f"  [CACHE] Done. {len(self._posting_cache)} terms cached.")


    @classmethod
    def exists(cls, directory: str) -> bool:
        if not os.path.exists(directory):
            return False
        index_path = os.path.join(directory, "index.db")
        lengths_path = os.path.join(directory, "doc_lengths.pkl")
        metadata_path = os.path.join(directory, "metadata.pkl")
        return (
                os.path.exists(index_path) and
                os.path.exists(lengths_path) and
                os.path.exists(metadata_path)
        )

    @classmethod
    def load(cls, directory: str, tokenizer=None) -> 'PositionalIndex':
        if not cls.exists(directory):
            raise FileNotFoundError(f"No index found at {directory}")

        index = cls.__new__(cls)  # skip __init__ entirely
        index.tokenizer = tokenizer
        index.index_dir = directory
        index._doc_lengths = {}
        index._doc_count = 0
        index._chunk_index = {}
        index._index = None
        index._posting_cache = {}

        index._db_path = os.path.join(directory, "index.db")
        index._conn = sqlite3.connect(index._db_path)
        index._conn.execute("PRAGMA journal_mode=WAL")
        index._conn.execute("PRAGMA cache_size=-64000")
        index._use_sqlite = True
        print(f"  📀 Loaded disk-backed index from {os.path.abspath(index._db_path)} (lazy)")

        lengths_path = os.path.join(directory, "doc_lengths.pkl")
        metadata_path = os.path.join(directory, "metadata.pkl")

        if os.path.exists(lengths_path):
            with open(lengths_path, "rb") as f:
                index._doc_lengths = pickle.load(f)

        if os.path.exists(metadata_path):
            with open(metadata_path, "rb") as f:
                metadata = pickle.load(f)
                index._doc_count = metadata.get("doc_count", 0)

        return index

    def get_posting_lists_bulk(self, terms: list[str]) -> dict[str, PostingList]:
        if not terms:
            return {}
        result = {}
        uncached = []

        for term in terms:
            if term in self._posting_cache:
                result[term] = self._posting_cache[term]
            else:
                uncached.append(term)

        if uncached:
            for i in range(0, len(uncached), 999):
                batch = uncached[i:i+999]
                placeholders = ','.join('?' * len(batch))
                rows = self._conn.execute(
                    f"SELECT term, data FROM postings WHERE term IN ({placeholders})", batch
                ).fetchall()
                for term, data in rows:
                    result[term] = pickle.loads(data)

        return result



    def build_docid_cache(self):
        columns = [row[1] for row in self._conn.execute("PRAGMA table_info(postings)").fetchall()]
        if 'doc_ids_blob' not in columns:
            self._conn.execute("ALTER TABLE postings ADD COLUMN doc_ids_blob BLOB")
            self._conn.commit()

        # Skip already-done terms
        done_count = self._conn.execute(
            "SELECT COUNT(*) FROM postings WHERE doc_ids_blob IS NOT NULL"
        ).fetchone()[0]
        print(f"  Resuming from {done_count:,} already done")

        cursor = self._conn.execute(
            "SELECT term, data FROM postings WHERE doc_ids_blob IS NULL"
        )
        batch = []
        count = done_count
        for term, data in cursor:
            pl = pickle.loads(data)
            doc_ids_set = pl.doc_ids()
            batch.append((pickle.dumps(doc_ids_set), term))
            if len(batch) >= 1000:
                self._conn.executemany(
                    "UPDATE postings SET doc_ids_blob = ? WHERE term = ?", batch
                )
                self._conn.commit()
                count += len(batch)
                print(f"  ... {count:,} terms updated")
                batch = []
        if batch:
            self._conn.executemany(
                "UPDATE postings SET doc_ids_blob = ? WHERE term = ?", batch
            )
            self._conn.commit()
            count += len(batch)
        print(f"  Done. {count:,} terms updated with doc_id cache.")

    def ensure_docid_cache(self):
        columns = [row[1] for row in self._conn.execute("PRAGMA table_info(postings)").fetchall()]
        if 'doc_ids_blob' not in columns:
            print(f"  Building doc_id cache for {os.path.abspath(self._db_path)}...")
            self.build_docid_cache()
        else:
            missing = self._conn.execute(
                "SELECT COUNT(*) FROM postings WHERE doc_ids_blob IS NULL"
            ).fetchone()[0]
            if missing > 0:
                print(f"  Completing doc_id cache ({missing:,} remaining) for {os.path.abspath(self._db_path)}...")
                self.build_docid_cache()
            else:
                print(f"  doc_id cache OK for {os.path.abspath(self._db_path)}")
    def get_doc_ids_bulk(self, terms: list[str]) -> dict[str, set[str]]:
        """Fetch only doc_id sets — much faster than full posting list deserialize."""
        if not terms:
            return {}
        result = {}
        for i in range(0, len(terms), 999):
            batch = terms[i:i+999]
            placeholders = ','.join('?' * len(batch))
            rows = self._conn.execute(
                f"SELECT term, doc_ids_blob FROM postings WHERE term IN ({placeholders})", batch
            ).fetchall()
            for term, blob in rows:
                if blob:
                    result[term] = pickle.loads(blob)
        return result


    def create_phoneme_tables(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS phoneme_documents (
                document_id TEXT PRIMARY KEY,
                phonemes BLOB,
                phoneme_length INTEGER
            )
        """)
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS phoneme_trigrams (
                trigram_id INTEGER,
                document_id TEXT
            )
        """)
        self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_trigram_id ON phoneme_trigrams(trigram_id)
        """)
        self._conn.commit()

    def insert_phoneme_data(self, doc_batch, tri_batch):
        """Insert pre-computed phoneme data into index.db"""
        if doc_batch:
            self._conn.executemany(
                "INSERT OR IGNORE INTO phoneme_documents VALUES (?, ?, ?)", doc_batch
            )
        if tri_batch:
            self._conn.executemany(
                "INSERT OR IGNORE INTO phoneme_trigrams VALUES (?, ?)", tri_batch
            )
        self._conn.commit()

    def get_trigrams(self, threshold, query_trigrams):
        """Query phoneme trigrams from index.db"""
        if not query_trigrams:
            return []
        placeholders = ','.join('?' * len(query_trigrams))
        rows = self._conn.execute(f"""
            SELECT document_id, COUNT(document_id) as overlap_count
            FROM phoneme_trigrams
            WHERE trigram_id IN ({placeholders})
            GROUP BY document_id
            HAVING overlap_count >= ?
            ORDER BY overlap_count DESC
            LIMIT 1000
        """, list(query_trigrams) + [threshold]).fetchall()
        from collections import namedtuple
        Result = namedtuple('Result', ['document_id', 'overlap_count'])
        return [Result(row[0], row[1]) for row in rows]

    def get_phoneme_data(self, candidates):
        """Query phoneme sequences from index.db"""
        if not candidates:
            return []
        from collections import namedtuple
        Result = namedtuple('Result', ['document_id', 'phonemes'])
        results = []
        for i in range(0, len(candidates), 999):
            batch = candidates[i:i+999]
            placeholders = ','.join('?' * len(batch))
            rows = self._conn.execute(f"""
                SELECT document_id, phonemes FROM phoneme_documents
                WHERE document_id IN ({placeholders})
            """, batch).fetchall()
            results.extend([Result(row[0], row[1]) for row in rows])
        return results

    def close(self) -> None:
        if self._conn:
            self._conn.close()