import time
import re
from pathlib import Path
from core.tokenizer import Tokenizer
from core.index import PositionalIndex
from core.models import Document, SearchResult
from core import lyrics_snippets                         # new import
from pipelines.ingestion import IngestionPipeline
from pipelines.query import QueryPipeline
from ranking.base import RankingStrategy
from ranking.proximity import ProximityBM25Ranking
from ranking.tfidf import TFIDFRanking             # new import
from repository.document_repo import DocumentRepository
import os
import re
from nltk.corpus import cmudict
from tqdm import tqdm


class SearchEngine:
    """
    Search engine with three-tier startup:

      1. Load saved index from disk
      2. Rebuild index from SQLite
      3. Import CSV then build index (slowest — first run only)
    """

    DEFAULT_INDEX_DIR_EN = "search_index_en"
    DEFAULT_INDEX_DIR_ES = "search_index_es"

    def __init__(
            self,
            index_dir_en: str | None = None,
            index_dir_es: str | None = None,
            ranker: RankingStrategy | None = None,
    ):
        self.tokenizer = Tokenizer()
        self.repository = DocumentRepository()
        self.ranker = ranker or TFIDFRanking()

        self.index_dir_en = index_dir_en or self.DEFAULT_INDEX_DIR_EN
        self.index_dir_es = index_dir_es or self.DEFAULT_INDEX_DIR_ES

        if PositionalIndex.exists(self.index_dir_en):
            print(f" Found saved English index at {os.path.abspath(self.index_dir_en)}")
            self.index_en = PositionalIndex.load(self.index_dir_en, self.tokenizer)
            self.index_en.ensure_docid_cache()
            self.index_en.warm_cache(top_n=50)
        else:
            self.index_en = PositionalIndex(self.tokenizer)

        if PositionalIndex.exists(self.index_dir_es):
            print(f" Found saved Spanish index at {os.path.abspath(self.index_dir_es)}")
            self.index_es = PositionalIndex.load(self.index_dir_es, self.tokenizer)
            self.index_es.ensure_docid_cache()
            self.index_es.warm_cache(top_n=50)
        else:
            self.index_es = PositionalIndex(self.tokenizer)

        self.ingestion = IngestionPipeline(
            self.tokenizer, self.repository, self.index_en, self.index_es
        )
        self.query_pipeline = QueryPipeline(
            self.tokenizer, self.index_en, self.repository, self.ranker
        )

    def import_csv(
            self,
            csv_path: str,
            max_rows: int | None = None,
            language_filter: str | None = None,
            save_index: bool = True,
            rebuild: bool = True,
    ) -> int:
        print(f"📥 Phase 1: Importing CSV → SQLite...")

        def on_import_progress(imported, seen):
            print(f"  Imported {imported:,} songs (scanned {seen:,} rows)", end="\r")

        imported = self.repository.import_csv(
            csv_path,
            max_rows=max_rows,
            language_filter=language_filter,
            on_progress=on_import_progress,
        )
        print(f"\n  ✓ Imported {imported:,} songs into SQLite")
        if rebuild:
            self.rebuild_index()
        if save_index:
            self.save_index()
        return imported


    def build_phoneme_index(self):

        print(" Building phoneme index...")
        self.index_en.create_phoneme_tables()

        CMU = cmudict.dict()
        CLEAN_CMU = {word: [re.sub(r"\d", "", p) for p in phones[0]] for word, phones in CMU.items()}
        PHONEMES = ["AA","AE","AH","AO","AW","AY","B","CH","D","DH","EH","ER","EY",
                    "F","G","HH","IH","IY","JH","K","L","M","N","NG","OW","OY","P",
                    "R","S","SH","T","TH","UH","UW","V","W","Y","Z","ZH"]
        PHONEME_TO_ID = {p: i for i, p in enumerate(PHONEMES)}

        batch_size = 100
        offset = 0
        count = 0
        total_docs = self.repository.count()

        with tqdm(total=total_docs, desc="Building Phonemes", unit="doc") as pbar:
            while True:
                docs = self.repository.get_batch(offset=offset, limit=batch_size)
                if not docs:
                    break
                
                tqdm.write(f"  [Phoneme Indexer] Processing {len(docs)} documents at offset {offset}...")

                doc_batch = []
                tri_batch = []

                for doc in docs:
                    if doc.tag == 'misc':
                        pbar.update(1)
                        continue

                    text_content = f"{doc.title or ''} {doc.content or ''}"
                    words = re.findall(r"[a-zA-Z']+", text_content.lower())

                    phoneme_ints = []
                    for w in words:
                        phones = CLEAN_CMU.get(w)
                        if phones:
                            for p in phones:
                                p_id = PHONEME_TO_ID.get(p)
                                if p_id is not None:
                                    phoneme_ints.append(p_id)

                    if not phoneme_ints:
                        pbar.update(1)
                        continue

                    doc_batch.append((doc.id, bytes(phoneme_ints), len(phoneme_ints)))

                    trigram_ids = set(
                        phoneme_ints[i]*1600 + phoneme_ints[i+1]*40 + phoneme_ints[i+2]
                        for i in range(len(phoneme_ints)-2)
                    )
                    for t in trigram_ids:
                        tri_batch.append((t, doc.id))
                        
                    pbar.update(1)

                tqdm.write(f"  [Phoneme Indexer] Committing {len(doc_batch)} phoneme records to SQLite...")
                self.index_en.insert_phoneme_data(doc_batch, tri_batch)
                count += len(doc_batch)
                offset += len(docs)
                # print(f"  ... {count:,} docs processed")

        print(f"  Phoneme index done. {count:,} docs.")



    def rebuild_index(self, max_docs: int | None = None, rebuild_en: bool = True, rebuild_es: bool = True) -> int:
        print(f"\n📥 Building search index from database...")

        if rebuild_en:
            self.index_en = PositionalIndex(self.tokenizer, index_dir=self.index_dir_en)
        if rebuild_es:
            self.index_es = PositionalIndex(self.tokenizer, index_dir=self.index_dir_es)
        self.ingestion = IngestionPipeline(
            self.tokenizer, self.repository, self.index_en, self.index_es
        )
        self.query_pipeline = QueryPipeline(
            self.tokenizer, self.index_en, self.repository, self.ranker
        )

        def on_index_progress(indexed, total, rate):
            remaining = total - indexed
            eta_sec = remaining / rate if rate > 0 else 0
            eta_min = eta_sec / 60
            print(f"  Indexed {indexed:,}/{total:,} ({rate:.0f} docs/sec) | ETA: {eta_min:.1f} min", end="\r")

        start = time.perf_counter()
        indexed = self.ingestion.ingest_from_repository(
            on_progress=on_index_progress,
            max_docs=max_docs,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        print(f"\n  ✓ Indexed {indexed:,} songs in {elapsed_ms:.1f}ms ({elapsed_ms/1000:.2f}s)")
        print(f"     EN index: {self.index_en.num_terms:,} unique terms")
        print(f"     ES index: {self.index_es.num_terms:,} unique terms")

        # Build doc_ids_blob cache
        print(f"\n Building doc_id caches...")
        self.index_en.ensure_docid_cache()
        self.index_es.ensure_docid_cache()

        self.build_phoneme_index()

        return indexed

    def save_index(self, save_en: bool = True, save_es: bool = True) -> dict:
        print(f"\n💾 Saving indexes to disk...")
        result = {}
        if save_en:
            result["en"] = self.index_en.save(self.index_dir_en)
        if save_es:
            result["es"] = self.index_es.save(self.index_dir_es)
        return result

    def add_document(self, id: str, title: str, content: str, **kwargs) -> None:
        doc = Document(id=id, title=title, content=content, **kwargs)
        self.ingestion.ingest(doc)

    def stats(self) -> dict:
        repo_stats = self.repository.stats()
        return {
            **repo_stats,
            "index_terms_en": self.index_en.num_terms,
            "index_docs_en": self.index_en.doc_count,
            "index_terms_es": self.index_es.num_terms,
            "index_docs_es": self.index_es.doc_count,
        }

    def close(self) -> None:
        if hasattr(self.index_en._index, 'close'):
            self.index_en._index.close()
        if hasattr(self.index_es._index, 'close'):
            self.index_es._index.close()
        self.repository.close()
    # ── Search ────────────────────────────────────────────────

    def search(
            self,
            query: str,
            top_k: int = 10,
            mode: str = 'cascade',
            weights: dict | None = None,
            filter_language: str | None = None,
            filter_artist: str | None = None,
            filter_tag: str | None = None,
            isSpanish: bool = False,
            #-----------add is spanish tag that will go as an attribute to ._cascade_search------------#
    ) -> list[dict] | list[SearchResult]:
        if mode == 'cascade':
            if isSpanish:
                return self._cascade_search(query, top_k, weights, isSpanish=True)
            else:
                return self._cascade_search(query, top_k, weights)
        elif mode == 'boolean':
            return self._boolean_search(query, top_k)
        else:
            return self._bm25_search(query, top_k, filter_language, filter_artist, filter_tag)



    def _cascade_search(
            self,
            query: str,
            top_k: int = 10,
            weights: dict | None = None,
            isSpanish: bool = False,
            # -----add the spanish tag that will go to query pipline
    ) -> list[dict]:
        """
        Cascade search — returns lyric snippets with metadata.
        This matches the behaviour of the original search engine.
        """
        print(f"[DEBUG] Using cascade search for: '{query}'")
        # Step 1: score and rank

        # querry pipline chage self.index to index_es
        if isSpanish:
            self.query_pipeline.index = self.index_es
            print(f"[DEBUG] Using ES index with {self.index_es.num_terms:,} terms and {self.index_es.doc_count:,} docs")
            results = self.query_pipeline.cascade_search(
                query, weights=weights, max_results=top_k * 5, isSpanish=True
            )
            query_terms = self.tokenizer.tokenize(query, for_spanish=True)
        else:
            self.query_pipeline.index = self.index_en
            print(f"[DEBUG] Using EN index with {self.index_en.num_terms:,} terms and {self.index_en.doc_count:,} docs")
            results = self.query_pipeline.cascade_search(
                query, weights=weights, max_results=top_k * 5
                # fetch more than needed so we have room to pick best snippets
            )
            print(f"[DEBUG] Cascade search returned {len(results)} results before snippet extraction")
            query_terms = self.tokenizer.tokenize(query)



        # Step 2: get query terms for tuple conversion
        # -------- add flag to use spanish for tokenizer


        # Step 3: convert scored results to (doc_id, position) tuples
        tuples = self.query_pipeline.cascade_results_to_tuples(
            results, query_terms, top_n=top_k
        )
        print(f"[DEBUG] Converted to {len(tuples)} (doc_id, position) tuples: {tuples[:5]}...")
        # Step 4: fetch documents and extract lyric snippets
        # this is where lyrics are actually retrieved from SQLite
        if isSpanish:
            return lyrics_snippets.build_results(
                tuples, self.repository, self.tokenizer.stop_words_spanish
            )
        else:
            return lyrics_snippets.build_results(
                tuples, self.repository, self.tokenizer.stop_words
            )

    def _boolean_search(self, query: str, top_k: int = 10) -> list[dict]:


        # Step 1: get matching documents
        results = self.query_pipeline.boolean_search(query, top_k)

        if not results:
            return []

        # Step 2: strip AND/OR/NOT and tokenize real words
        cleaned = re.sub(r'\b(AND|OR|NOT)\b', '', query)
        query_terms = self.tokenizer.tokenize(cleaned)

        # Step 3: find first position of any query term per doc
        tuples = []
        for r in results:
            doc_id = r.document.id
            position = None

            for term in query_terms:
                positions = self.index_en.term_positions(term, doc_id)
                if positions:
                    position = min(positions)
                    break

            if position is not None:
                tuples.append((doc_id, position))

        # Step 4: extract snippets
        return lyrics_snippets.build_results(
            tuples, self.repository, self.tokenizer.stop_words
        )
    def _bm25_search(
            self,
            query: str,
            top_k: int = 10,
            filter_language: str | None = None,
            filter_artist: str | None = None,
            filter_tag: str | None = None,
    ) -> list[SearchResult]:
        """
        Original BM25/proximity search — returns SearchResult objects.
        Unchanged from before.
        """
        fetch_size = top_k * 5 if any([filter_language, filter_artist, filter_tag]) else top_k
        results = self.query_pipeline.search(query, top_k=fetch_size)

        if any([filter_language, filter_artist, filter_tag]):
            filter_kwargs = {}
            if filter_language:
                filter_kwargs["language"] = filter_language
            if filter_artist:
                filter_kwargs["artist"] = filter_artist
            if filter_tag:
                filter_kwargs["tag"] = filter_tag

            allowed_ids = self.repository.get_doc_ids_for_filter(**filter_kwargs)
            results = [r for r in results if r.document.id in allowed_ids]

        return results[:top_k]