import sys
import time
from engine import SearchEngine
from pathlib import Path
from importlib import reload
import ranking.tfidf as tfidf_mod
import ranking.bm25 as bm25_mod
import pipelines.query as query_mod
import core.lyrics_snippets as lyrics_mod
import engine as engine_mod


# For testing Search engine locally without api
def main():
    BASE = Path(__file__).parent.parent / "data"
    # csv_path_en = sys.argv[1] if len(sys.argv) > 1 else str(BASE / "songs_en.csv")
    # csv_path_es = sys.argv[2] if len(sys.argv) > 2 else str(BASE / "songs_es.csv")

    # db_path="songs.db",

    engine = SearchEngine( index_dir_en="search_index_en", index_dir_es="search_index_es")

    en_ready = engine.index_en.doc_count > 0
    es_ready = engine.index_es.doc_count > 0
    print(f"EN index: {engine.index_en.doc_count:,} docs")
    print(f"ES index: {engine.index_es.doc_count:,} docs")


    if en_ready and es_ready:
        print(f"✅ Ready! EN: {engine.index_en.doc_count:,} docs, ES: {engine.index_es.doc_count:,} docs\n")

    elif engine.repository.count() > 0:
        print(f"Found {engine.repository.count():,} songs in database, rebuilding missing indexes...\n")
        engine.rebuild_index(rebuild_en=not en_ready, rebuild_es=not es_ready)
        engine.save_index(save_en=not en_ready, save_es=not es_ready)

    else:
        csv_path_en = r"C:\Users\ander\Documents\GitHub\TTDS-CW3\data\songs_en.csv"
        csv_path_es = r"C:\Users\ander\Documents\GitHub\TTDS-CW3\data\songs_es.csv"
        print(f"First run — importing CSVs\n")
        engine.import_csv(csv_path_en, language_filter="en", save_index=False, rebuild=False)
        engine.import_csv(csv_path_es, language_filter="es", save_index=False, rebuild=False)
        engine.rebuild_index()
        engine.save_index()

    # ── Show stats ────────────────────────────────────────────
    # stats = engine.stats()
    # print("📊 Corpus Statistics")
    # print("-" * 40)
    # for key, value in stats.items():
    #     if isinstance(value, float):
    #         print(f"  {key:20}: {value:,.1f}")
    #     elif isinstance(value, int):
    #         print(f"  {key:20}: {value:,}")
    #     else:
    #         print(f"  {key:20}: {value}")

    # ── Test searches ─────────────────────────────────────────
    test_queries = [
        # ("love and heartbreak", 'cascade', 'en'),
        # ("dancing in the moonlight", 'cascade', 'en'),
        # ("had secondhands mom bounced on old man", 'cascade', 'en'),
        # ("love AND heartbreak", 'boolean', 'en'),
        # ("love AND NOT sad", 'boolean', 'en'),
        # ("dance OR sing", 'boolean', 'en'),
        # ("Que se preparen que lo que viene es pa' que le den", 'cascade', 'es'),
         ("All of the lights", 'cascade', 'en'),
         ("Olive delights", 'cascade', 'en'),
        #("had secondhands moms bounced on old man", 'cascade', 'en')

    ]

    print("engien has been initiliazed starign querries")
    for query, mode , language in test_queries:
        print(f"\n{'=' * 70}")
        print(f"🔍 \"{query}\" [{mode}]")
        print("-" * 70)

        start = time.perf_counter()
        #-------------------------------add is spanish tag that will go to engine--------#
        if language == 'es':
            results = engine.search(query, top_k=5, mode=mode, isSpanish = True)
        else:
            results = engine.search(query, top_k=5, mode=mode, isSpanish = False)
        #-------------------------------------------------------------------------------#
        elapsed_ms = (time.perf_counter() - start) * 1000

        if not results:
            print(f"  No results found. ({elapsed_ms:.1f}ms)")
            continue

        for i, r in enumerate(results, 1):
            year_str = f" ({r['year']})" if r.get('year') else ""
            print(f"  {i}. {r['title']}{year_str}")
            print(f"     🎤 {r['artist']}")
            print(f"     ♪  {r['lyric_snippet']}")

        print(f"\n  ⏱️  {elapsed_ms:.1f}ms | {len(results)} results")

    # ── Interactive mode ──────────────────────────────────────
    print(f"\n{'=' * 70}")
    print("🎵 Interactive Search (type 'quit' to exit)")
    print("   Boolean: love AND heartbreak | love OR hate | love AND NOT sad")
    print("   Cascade: love and heartbreak")
    print("   Commands: :save  :rebuild  :stats")
    print("=" * 70)

    while True:
        try:
            raw = input("\n🔍 > ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if raw.lower() in ("quit", "exit", "q"):
            break

        if not raw:
            continue

        # Handle commands
        if raw == ":save":
            engine.save_index()
            continue
        elif raw == ":rebuild":
            engine.rebuild_index()
            engine.save_index()
            continue
        elif raw == ":stats":
            for k, v in engine.stats().items():
                print(f"  {k}: {v}")
            continue
        elif raw == ":reload":
            reload(bm25_mod)
            reload(tfidf_mod)
            reload(lyrics_mod)
            reload(query_mod)
            reload(engine_mod)

            engine.query_pipeline = query_mod.QueryPipeline(
                tokenizer=engine.tokenizer,
                index=engine.index_en,
                repository=engine.repository,
                ranker=tfidf_mod.TFIDFRanking()
            )
            print("✅ Reloaded ranking + query pipeline")
            continue
        elif raw == ":debug":
            import debug
            debug.DEBUG_LEVEL = (debug.DEBUG_LEVEL +1)%4
            print(f"✅ Debug level: {debug.DEBUG_LEVEL}")
            continue

        # auto-detect boolean vs cascade
        # uppercase AND/OR/NOT → boolean, everything else → cascade
        boolean_terms = {"AND", "OR", "NOT"}
        mode = 'boolean' if any(w in boolean_terms for w in raw.split()) else 'cascade'

        start = time.perf_counter()
        results = engine.search(raw, top_k=10, mode=mode)
        elapsed_ms = (time.perf_counter() - start) * 1000

        if not results:
            print(f"  No results found. ({elapsed_ms:.1f}ms)")
            continue

        for i, r in enumerate(results, 1):
            year_str = f" ({r['year']})" if r.get('year') else ""
            print(f"  {i}. {r['title']}{year_str}")
            print(f"     🎤 {r['artist']}")
            print(f"     ♪  {r['lyric_snippet']}")

        print(f"\n  ⏱️  {elapsed_ms:.1f}ms | {len(results)} results")

    engine.close()
    print("\n👋 Goodbye!")


if __name__ == "__main__":
    main()