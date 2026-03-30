import time
from core.models import Document
from core.tokenizer import Tokenizer
from core.index import PositionalIndex
from repository.document_repo import DocumentRepository



class IngestionPipeline:
    """Pipeline: Documents → Tokenize → Store → Index"""

    def __init__(
            self,
            tokenizer: Tokenizer,
            repository: DocumentRepository,
            index_en: PositionalIndex,
            index_es: PositionalIndex,
    ):
        self.tokenizer = tokenizer
        self.repository = repository
        self.index_en = index_en
        self.index_es = index_es

    def _is_spanish(self, doc: Document) -> bool:
        return doc.language == 'es'

    def _is_english(self, doc: Document) -> bool:
        return doc.language == 'en' or doc.language == '' or doc.language is None

    def _tokenize(self, doc: Document) -> list[str]:
        for_spanish = self._is_spanish(doc)
        return self.tokenizer.tokenize(f"{doc.title} {doc.content}", for_spanish=for_spanish)

    def _get_index(self, doc: Document) -> PositionalIndex:
        if self._is_spanish(doc):
            return self.index_es
        return self.index_en

    def ingest(self, doc: Document) -> None:
        """Index a single document."""
        doc.tokens = self._tokenize(doc)
        self.repository.add(doc)
        self._get_index(doc).add_document(doc.id, doc.tokens)

    def ingest_from_repository(
            self,
            batch_size: int = 150,
            max_docs: int | None = None,
            on_progress: callable = None,
    ) -> int:
        from tqdm import tqdm
        
        total = self.repository.count()
        if max_docs:
            total = min(total, max_docs)

        indexed = 0
        skipped = 0
        offset = 0
        start = time.perf_counter()

        with tqdm(total=total, desc="Indexing Documents", unit="doc") as pbar:
            while True:
                if max_docs and indexed >= max_docs:
                    break

                batch = self.repository.get_batch(offset=offset, limit=batch_size)
                if not batch:
                    break
                    
                tqdm.write(f"  [Indexer] Tokenising and indexing batch size {len(batch)} at offset {offset}...")

                for doc in batch:
                    if max_docs and indexed >= max_docs:
                        break
                    try:
                        if doc.tag == 'misc':
                            skipped += 1
                            pbar.update(1)
                            continue
                        doc.tokens = self._tokenize(doc)
                        self._get_index(doc).add_document(doc.id, doc.tokens)
                        indexed += 1
                        pbar.update(1)
                    except Exception as e:
                        skipped += 1
                        pbar.update(1)
                        # tqdm.write(f"  ⚠️ Skipping doc {doc.id}: {e}")
                        continue

                self.index_en.flush_chunk()
                self.index_es.flush_chunk()
                tqdm.write(f"  [Indexer] Flushed index chunks to disk.")

                offset += len(batch)

        elapsed = time.perf_counter() - start
        if skipped > 0:
            print(f"\n  ⚠️ Skipped {skipped:,} malformed documents")
        if on_progress:
            rate = indexed / elapsed if elapsed > 0 else 0
            on_progress(indexed, total, rate)

        return indexed