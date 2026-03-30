import time
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from engine import SearchEngine


def create_app(
    db_path: str = "",
    index_dir: str = "search_index",
    csv_path: str | None = None,
    max_import_rows: int | None = None,
    language_filter: str | None = None,
) -> Flask:
    print("🚀 Initializing Flask application...", flush=True)
    """
    Application factory for the search engine API.

    Usage:
        app = create_app(db_path="songs.db")
        app.run(debug=True)
    """

    cors_origins: list[str] = [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:8080",
        ]

    app = Flask(__name__)
        # Enable CORS for all routes
    CORS(
        app,
        resources={
            r"/*": {
                "origins": cors_origins,
                "methods": ["GET", "POST", "OPTIONS"],
                "allow_headers": ["Content-Type"],
                "supports_credentials": True,
            }
        },
    )

    # ── Initialise the engine ────────────────────────────────

    index_dir_en = f"{index_dir}_en"
    index_dir_es = f"{index_dir}_es"
    engine = SearchEngine(index_dir_en=index_dir_en, index_dir_es=index_dir_es)

    if engine.repository.count() > 0:
        print(f"📥 Rebuilding index from database...")
        engine.rebuild_index()
        engine.save_index()

        indexed_docs = engine.index_en.doc_count + engine.index_es.doc_count
        indexed_terms = engine.index_en.num_terms + engine.index_es.num_terms
        print(f"✅ Index rebuilt ({indexed_docs:,} docs, {indexed_terms:,} terms)")

    elif csv_path:
        print(f"📥 First run — importing {csv_path}")
        engine.import_csv(
            csv_path,
            max_rows=max_import_rows,
            language_filter=language_filter,
            save_index=True,
        )
    else:
        print("⚠️  No data loaded. Use POST /index/import to load a CSV.")

    # ── Middleware ────────────────────────────────────────────

    @app.after_request
    def add_timing_header(response):
        """Add server timing to every response."""
        if hasattr(request, "_start_time"):
            elapsed_ms = (time.perf_counter() - request._start_time) * 1000
            response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.2f}"
        return response

    @app.before_request
    def start_timer():
        request._start_time = time.perf_counter()

    # ── Search Endpoints ─────────────────────────────────────

    @app.route("/api/search", methods=["GET"])
    def search():
        """
        Search for documents.

        Query parameters:
            q           (required)  Search query. Use quotes for phrases: "broken heart"
            top_k       (optional)  Number of results (default: 10, max: 100)
            query_language (optional) Query language from UI toggle, e.g. "en" or "es"
            language    (optional)  Explicit language filter, e.g. "en"
            artist      (optional)  Filter by artist name
            tag         (optional)  Filter by tag/genre, e.g. "pop"

        Example:
            GET /search?q=love+and+heartbreak&top_k=5
            GET /search?q="broken+heart"&query_language=en&tag=pop
        """
        query = request.args.get("q", "").strip()
        if not query:
            return jsonify({"error": "Missing required parameter: q"}), 400

        top_k = request.args.get("top_k", 10, type=int)
        top_k = min(max(top_k, 1), 100)

        query_language = request.args.get("query_language")
        filter_language = request.args.get("language")

        filters = {}
        if query_language:
            filters["query_language"] = query_language
        if filter_language:
            filters["filter_language"] = filter_language
        if request.args.get("artist"):
            filters["filter_artist"] = request.args["artist"]
        if request.args.get("tag"):
            filters["filter_tag"] = request.args["tag"]

        start = time.perf_counter()
        results = engine.search(query, top_k=top_k, **filters)
        search_time_ms = (time.perf_counter() - start) * 1000

        return jsonify({
            "query": query,
            "query_language": query_language,
            "filters": {k.replace("filter_", ""): v for k, v in filters.items()},
            "found": len(results),
            "search_time_ms": round(search_time_ms, 2),
            "hits": [
                {
                    "id": r.document.id,
                    "score": round(r.score, 4),
                    "proximity_score": round(r.proximity_score, 4),
                    "phrase_matched": r.phrase_matched,
                    "document": {
                        "title": r.document.title,
                        "artist": r.document.artist,
                        "tag": r.document.tag,
                        "year": r.document.year,
                        "views": r.document.views,
                        "features": r.document.features,
                        "language": r.document.language,
                        "lyrics_preview": r.document.short_lyrics(200),
                    },
                }
                for r in results
            ],
        })

    # ── Document Endpoints ───────────────────────────────────

    @app.route("/api/documents/<doc_id>", methods=["GET"])
    def get_document(doc_id):
        """
        Get a single document by ID.

        Example:
            GET /documents/12345
        """
        doc = engine.repository.get(doc_id)
        if not doc:
            return jsonify({"error": f"Document not found: {doc_id}"}), 404

        return jsonify({
            "id": doc.id,
            "title": doc.title,
            "artist": doc.artist,
            "tag": doc.tag,
            "year": doc.year,
            "views": doc.views,
            "features": doc.features,
            "language": doc.language,
            "lyrics": doc.content,
        })

    @app.route("/api/documents", methods=["POST"])
    def add_document():
        """
        Add a single document to the index.

        Body (JSON):
            {
                "id": "unique-id",
                "title": "Song Title",
                "lyrics": "Song lyrics...",
                "artist": "Artist Name",
                "tag": "pop",
                "year": 2024,
                "views": 1000000
            }

        Example:
            POST /documents
        """
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        required = ["id", "title", "lyrics"]
        missing = [f for f in required if not data.get(f)]
        if missing:
            return jsonify({"error": f"Missing required fields: {missing}"}), 400

        doc = engine.add_document(
            id=data["id"],
            title=data["title"],
            content=data["lyrics"],
            artist=data.get("artist", ""),
            tag=data.get("tag", ""),
            year=data.get("year"),
            views=data.get("views"),
            features=data.get("features", ""),
            language=data.get("language", ""),
        )

        return jsonify({
            "message": "Document indexed successfully",
            "id": data["id"],
        }), 201

    @app.route("/api/documents/<doc_id>", methods=["DELETE"])
    def delete_document(doc_id):
        """
        Delete a document from the repository.

        Note: This removes it from SQLite but the trie index
        retains it until the next rebuild. Use POST /index/rebuild
        to fully remove it from search results.

        Example:
            DELETE /documents/12345
        """
        deleted = engine.repository.delete(doc_id)
        if not deleted:
            return jsonify({"error": f"Document not found: {doc_id}"}), 404

        return jsonify({
            "message": "Document deleted from repository",
            "id": doc_id,
            "note": "Run POST /index/rebuild to remove from search index",
        })

    # ── Filter / Browse Endpoints ────────────────────────────

    @app.route("/api/documents/by-artist/<artist>", methods=["GET"])
    def by_artist(artist):
        """
        List documents by artist.

        Example:
            GET /documents/by-artist/drake
        """
        docs = engine.repository.filter_by_artist(artist)
        return jsonify({
            "artist": artist,
            "count": len(docs),
            "documents": [
                {
                    "id": d.id,
                    "title": d.title,
                    "year": d.year,
                    "tag": d.tag,
                    "views": d.views,
                }
                for d in docs
            ],
        })

    @app.route("/api/documents/top", methods=["GET"])
    def top_documents():
        """
        Get the most-viewed documents.

        Query parameters:
            limit   (optional)  Number of results (default: 10)

        Example:
            GET /documents/top?limit=20
        """
        limit = request.args.get("limit", 10, type=int)
        docs = engine.repository.top_by_views(limit)

        return jsonify({
            "count": len(docs),
            "documents": [
                {
                    "id": d.id,
                    "title": d.title,
                    "artist": d.artist,
                    "year": d.year,
                    "views": d.views,
                    "tag": d.tag,
                }
                for d in docs
            ],
        })

    # ── Index Management Endpoints ───────────────────────────

    @app.route("/api/index/stats", methods=["GET"])
    def index_stats():
        """
        Get corpus and index statistics.

        Example:
            GET /index/stats
        """
        return jsonify(engine.stats())

    @app.route("/api/index/rebuild", methods=["POST"])
    def rebuild_index():
        """
        Rebuild the search index from the database.

        Use this after adding/deleting documents to refresh search results.

        Example:
            POST /index/rebuild
        """
        start = time.perf_counter()
        count = engine.rebuild_index()
        engine.save_index()
        elapsed = time.perf_counter() - start

        return jsonify({
            "message": "Index rebuilt and saved",
            "documents_indexed": count,
            "terms": engine.index_en.num_terms + engine.index_es.num_terms,
            "elapsed_seconds": round(elapsed, 2),
        })

    @app.route("/api/index/save", methods=["POST"])
    def save_index():
        """
        Save the current index to disk.

        Example:
            POST /index/save
        """
        info = engine.save_index()
        return jsonify({
            "message": "Index saved",
            **info,
        })

    @app.route("/api/index/import", methods=["POST"])
    def import_csv():
        """
        Import documents from a CSV file.

        Body (JSON):
            {
                "csv_path": "/path/to/lyrics.csv",
                "max_rows": 5000,
                "language_filter": "en"
            }

        Example:
            POST /index/import
        """
        data = request.get_json()
        if not data or not data.get("csv_path"):
            return jsonify({"error": "Missing required field: csv_path"}), 400

        csv_path = data["csv_path"]
        if not os.path.exists(csv_path):
            return jsonify({"error": f"File not found: {csv_path}"}), 404

        start = time.perf_counter()

        imported = engine.import_csv(
            csv_path,
            max_rows=data.get("max_rows"),
            language_filter=data.get("language_filter"),
            save_index=True,
        )

        elapsed = time.perf_counter() - start

        return jsonify({
            "message": "Import complete",
            "documents_imported": imported,
            "terms": engine.index_en.num_terms + engine.index_es.num_terms,
            "elapsed_seconds": round(elapsed, 2),
        })

    # ── Health ───────────────────────────────────────────────

    @app.route("/api/health", methods=["GET"])
    def health():
        """Health check endpoint."""
        return jsonify({
            "status": "ok",
            "documents": engine.index_en.doc_count + engine.index_es.doc_count,
            "terms": engine.index_en.num_terms + engine.index_es.num_terms,
            "documents_en": engine.index_en.doc_count,
            "documents_es": engine.index_es.doc_count,
        })

    return app


# ── Run directly ─────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Song Lyrics Search Engine API")
    parser.add_argument("--db", default="songs.db", help="SQLite database path")
    parser.add_argument("--index-dir", default="search_index", help="Index directory")
    parser.add_argument("--csv", default=None, help="CSV file to import on first run")
    parser.add_argument("--max-rows", type=int, default=None, help="Max rows to import")
    parser.add_argument("--lang", default=None, help="Language filter for import")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=5000, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    app = create_app(
        db_path=args.db,
        index_dir=args.index_dir,
        csv_path=args.csv,
        max_import_rows=args.max_rows,
        language_filter=args.lang,
    )

    print(f"\n🚀 API running at http://{args.host}:{args.port}")
    print(f"   Docs: http://{args.host}:{args.port}/health\n")

    app.run(host=args.host, port=args.port, debug=args.debug)