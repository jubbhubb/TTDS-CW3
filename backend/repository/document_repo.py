import csv
import os
import threading
import urllib.parse
from pathlib import Path

from sqlalchemy import create_engine, select, func, or_, delete
from sqlalchemy.orm import sessionmaker, Session, scoped_session

from core.models import Base, Document


class DocumentRepository:
    """
    SQLAlchemy-backed document repository.

    Stores all document metadata in a relational database while
    providing the same interface the rest of the engine expects.
    Supports importing from your song lyrics CSV.
    """

    def __init__(self):
        """
        Initialise the repository.

        Args:
            db_path: Path to SQLite database file.
                     Use ":memory:" for an in-memory database (default).
                     Use a file path like "songs.db" for persistence.
        """
        
        # Load environment variables from .env file (if present)
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
            
        # Check for Google Cloud PostgreSQL credentials in environment
        db_user = os.environ.get("GOOGLE_DB_USER")
        db_password = os.environ.get("GOOGLE_DB_PASSWORD")
        db_host = os.environ.get("GOOGLE_DB_HOST")
        db_port = os.environ.get("GOOGLE_DB_PORT", "5432")
        db_name = os.environ.get("GOOGLE_DB_NAME", "postgres")

        # Configure database URL (Google Cloud is default if credentials exist)
        if db_user and db_password and db_host:
            # We have PostgreSQL credentials
            db_password = db_password.strip('"').strip("'")
            encoded_pwd = urllib.parse.quote_plus(db_password)
            db_url = f"postgresql+psycopg2://{db_user}:{encoded_pwd}@{db_host}:{db_port}/{db_name}"
            print(f"☁️  Connecting to Google Cloud PostgreSQL at {db_host}...")
        elif db_path == ":memory:":
            db_url = "sqlite://"
            print("💾 Connecting to Local SQLite (in-memory)...")
        else:
            # Ensure absolute path or correct relative path handling
            # SQLAlchemy needs 3 slashes for relative, 4 for absolute
            db_url = f"sqlite:///{db_path}"
            print(f"💾 Connecting to Local SQLite ({db_path})...")

        self.engine = create_engine(db_url)
        
        # Create tables
        Base.metadata.create_all(self.engine)
        
        # Create session factory
        # check_same_thread=False equivalent is handled by session scoping or pool management
        # For SQLite with multithreading, we generally want scoped sessions or careful management
        self._session_factory = sessionmaker(bind=self.engine)
        self._Session = scoped_session(self._session_factory)
        
        self._lock = threading.Lock()

    # ── Core CRUD ────────────────────────────────────────────

    def add(self, doc: Document) -> None:
        """Insert or replace a single document."""
        session = self._Session()
        try:
            session.merge(doc)
            session.commit()
        except:
            session.rollback()
            raise
        finally:
            session.close()

    def add_many(self, docs: list[Document]) -> None:
        """Batch insert documents."""
        session = self._Session()
        try:
            for doc in docs:
                session.merge(doc)
            session.commit()
        except:
            session.rollback()
            raise
        finally:
            session.close()

    def get(self, doc_id: str) -> Document | None:
        """Fetch a single document by ID."""
        session = self._Session()
        try:
            return session.get(Document, str(doc_id))
        finally:
            session.close()

    def get_many(self, doc_ids: list[str]) -> list[Document]:
        """Fetch multiple documents by ID. Preserves order."""
        if not doc_ids:
            return []
            
        session = self._Session()
        try:
            stmt = select(Document).where(Document.id.in_(doc_ids))
            results = session.execute(stmt).scalars().all()
            doc_map = {doc.id: doc for doc in results}
            return [doc_map[did] for did in doc_ids if did in doc_map]
        finally:
            session.close()

    def all(self) -> list[Document]:
        """Fetch all documents."""
        session = self._Session()
        try:
            stmt = select(Document)
            return list(session.execute(stmt).scalars().all())
        finally:
            session.close()

    def count(self) -> int:
        """Total number of documents."""
        session = self._Session()
        try:
            return session.scalar(select(func.count()).select_from(Document))
        finally:
            session.close()

    def delete(self, doc_id: str) -> bool:
        """Delete a document by ID."""
        session = self._Session()
        try:
            stmt = delete(Document).where(Document.id == doc_id)
            result = session.execute(stmt)
            session.commit()
            return result.rowcount > 0
        except:
            session.rollback()
            raise
        finally:
            session.close()

    # ── Filtering (SQL-powered) ──────────────────────────────

    def filter_by_artist(self, artist: str) -> list[Document]:
        """Find documents by artist (case-insensitive)."""
        session = self._Session()
        try:
            stmt = select(Document).where(func.lower(Document.artist) == artist.lower())
            return list(session.execute(stmt).scalars().all())
        finally:
            session.close()

    def filter_by_year(self, start: int, end: int | None = None) -> list[Document]:
        """Find documents within a year range."""
        if end is None:
            end = start
        session = self._Session()
        try:
            stmt = select(Document).where(Document.year.between(start, end))
            return list(session.execute(stmt).scalars().all())
        finally:
            session.close()

    def filter_by_language(self, language: str) -> list[Document]:
        """Find documents by language."""
        session = self._Session()
        try:
            stmt = select(Document).where(func.lower(Document.language) == language.lower())
            return list(session.execute(stmt).scalars().all())
        finally:
            session.close()

    def filter_by_tag(self, tag: str) -> list[Document]:
        """Find documents by tag/genre."""
        session = self._Session()
        try:
            stmt = select(Document).where(func.lower(Document.tag) == tag.lower())
            return list(session.execute(stmt).scalars().all())
        finally:
            session.close()

    def top_by_views(self, limit: int = 10) -> list[Document]:
        """Get the most-viewed documents."""
        session = self._Session()
        try:
            stmt = select(Document).where(Document.views != None).order_by(Document.views.desc()).limit(limit)
            return list(session.execute(stmt).scalars().all())
        finally:
            session.close()

    def get_doc_ids_for_filter(self, **kwargs) -> set[str]:
        """
        Generic filter returning just document IDs.
        """
        conditions = []
        
        for field, value in kwargs.items():
            if field in ("artist", "tag", "language", "language_cld3", "language_ft"):
                column = getattr(Document, field)
                conditions.append(func.lower(column) == value.lower())
            elif field == "year_min":
                conditions.append(Document.year >= value)
            elif field == "year_max":
                conditions.append(Document.year <= value)
            elif field == "views_min":
                conditions.append(Document.views >= value)

        if not conditions:
            return set()

        session = self._Session()
        try:
            stmt = select(Document.id).where(*conditions)
            return set(session.execute(stmt).scalars().all())
        finally:
            session.close()

    # ── Statistics ───────────────────────────────────────────

    def stats(self) -> dict:
        """Get corpus statistics."""
        session = self._Session()
        try:
            return {
                "total_docs": session.scalar(select(func.count()).select_from(Document)) or 0,
                "unique_artists": session.scalar(select(func.count(func.distinct(Document.artist))).select_from(Document)) or 0,
                "unique_tags": session.scalar(select(func.count(func.distinct(Document.tag))).select_from(Document)) or 0,
                "unique_languages": session.scalar(select(func.count(func.distinct(Document.language))).select_from(Document)) or 0,
                "min_year": session.scalar(select(func.min(Document.year)).select_from(Document)),
                "max_year": session.scalar(select(func.max(Document.year)).select_from(Document)),
                "avg_views": session.scalar(select(func.avg(Document.views)).select_from(Document)),
            }
        finally:
            session.close()

    # ── CSV Import ───────────────────────────────────────────

    def import_csv(
        self,
        csv_path: str,
        max_rows: int | None = None,
        language_filter: str | None = None,
        batch_size: int = 1000,
        on_progress: callable = None,
    ) -> int:
        """
        Import song lyrics from a CSV file.
        """
        csv_path = Path(csv_path)
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        imported = 0
        seen = 0
        batch: list[Document] = []

        with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)

            # Validate headers
            expected = {"title", "lyrics", "id"}
            if not expected.issubset(set(reader.fieldnames or [])):
                missing = expected - set(reader.fieldnames or [])
                raise ValueError(
                    f"CSV is missing required columns: {missing}. "
                    f"Found: {reader.fieldnames}"
                )

            for row in reader:
                seen += 1

                if max_rows and imported >= max_rows:
                    break

                # Get detected language
                row_lang = (
                    row.get("language", "")
                    or row.get("language_cld3", "")
                    or row.get("language_ft", "")
                )
                
                # Global restriction: only allow English or Spanish
                if row_lang.lower() not in ("en", "es"):
                    continue

                # Apply specific language filter if provided
                if language_filter:
                    if row_lang.lower() != language_filter.lower():
                        continue

                # Skip rows with empty lyrics or ID
                doc_id = row.get("id", "").strip()
                lyrics = row.get("lyrics", "").strip()
                if not doc_id or not lyrics:
                    continue

                doc = self._csv_row_to_doc(row)
                batch.append(doc)

                if len(batch) >= batch_size:
                    self.add_many(batch)
                    imported += len(batch)
                    batch.clear()

                    if on_progress:
                        on_progress(imported, seen)

            # Final batch
            if batch:
                self.add_many(batch)
                imported += len(batch)

                if on_progress:
                    on_progress(imported, seen)

        return imported

    # ── Internal helpers ─────────────────────────────────────

    def _csv_row_to_doc(self, row: dict) -> Document:
        """Convert a CSV row dict to a Document."""
        # Parse year safely
        year = None
        raw_year = row.get("year", "").strip()
        if raw_year:
            try:
                year = int(float(raw_year))
            except (ValueError, TypeError):
                pass

        # Parse views safely
        views = None
        raw_views = row.get("views", "").strip()
        if raw_views:
            try:
                views = int(float(raw_views))
            except (ValueError, TypeError):
                pass

        return Document(
            id=row.get("id", "").strip(),
            title=row.get("title", "").strip(),
            content=row.get("lyrics", "").strip(),
            artist=row.get("artist", "").strip(),
            tag=row.get("tag", "").strip(),
            year=year,
            views=views,
            features=row.get("features", "").strip(),
            language=row.get("language", "").strip(),
            language_cld3=row.get("language_cld3", "").strip(),
            language_ft=row.get("language_ft", "").strip(),
        )

    def close(self) -> None:
        """Close the database engine."""
        self._Session.remove()
        self.engine.dispose()


    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def get_batch(self, offset: int = 0, limit: int = 2000) -> list[Document]:
        session = self._Session()
        print(f"  [Repo] Fetching batch (offset={offset}, limit={limit})...")
        try:
            stmt = select(Document).order_by(Document.id).offset(offset).limit(limit)
            results = list(session.execute(stmt).scalars().all())
            print(f"  [Repo] Retrieved {len(results)} documents.")
            return results
        finally:
            session.close()

    def get_many_lightweight(self, doc_ids: list[str]) -> list:
        if not doc_ids:
            return []
        session = self._Session()
        print(f"  [Repo] Fetching lightweight data for {len(doc_ids)} docs...")
        try:
            all_results = []
            for i in range(0, len(doc_ids), 999):
                batch = doc_ids[i:i+999]
                stmt = select(Document.id, Document.views).where(Document.id.in_(batch))
                chunk = session.execute(stmt).fetchall()
                all_results.extend(chunk)
            print(f"  [Repo] Retrieved {len(all_results)} lightweight records.")
            return all_results
        finally:
            session.close()
    # def get_trigrams(self, threshold: int, query_trigrams):
    #     print(f"Filtering candidates from database (Threshold: {threshold})...")
    #     sessionMethod = self._Session()
    #
    #
    #     candidate_query = (
    #         sessionMethod.query(
    #             PhonemeTrigram.document_id,
    #             func.count(PhonemeTrigram.document_id).label('overlap_count')
    #         )
    #         .filter(PhonemeTrigram.trigram_id.in_(query_trigrams))
    #         .group_by(PhonemeTrigram.document_id)
    #         .having(func.count(PhonemeTrigram.document_id) >= threshold)
    #         .order_by(text('overlap_count DESC'))
    #         .limit(1000) # Safety cap to prevent scoring too many results
    #     ).all()
    #     return candidate_query
    # def get_phoneme_data(self, candidates: list) :
    #     sessionMethod = self._Session()
    #     phoneme_data = (
    #         sessionMethod.query(PhonemeDocument.document_id, PhonemeDocument.phonemes)
    #         .filter(PhonemeDocument.document_id.in_(candidates))
    #         .all()
    #     )
    #     return phoneme_data