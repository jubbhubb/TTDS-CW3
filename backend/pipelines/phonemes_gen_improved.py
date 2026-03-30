import re
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor
from itertools import islice

from tqdm import tqdm
import nltk
from nltk.corpus import cmudict
from sqlalchemy import create_engine, insert, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, insert, text

from core.phonemes import PhonemeBase, PhonemeDocument, PhonemeTrigram
from core.models import Document

# --- Global Cache for Workers ---
# We load this globally so every process has access to it via copy-on-write
nltk.download("cmudict", quiet=True)
_CMU_RAW = cmudict.dict()
CLEAN_CMU = {word: [re.sub(r"\d", "", p) for p in phones[0]] for word, phones in _CMU_RAW.items()}

PHONEMES = ["AA","AE","AH","AO","AW","AY","B","CH","D","DH","EH","ER","EY",
            "F","G","HH","IH","IY","JH","K","L","M","N","NG","OW","OY","P",
            "R","S","SH","T","TH","UH","UW","V","W","Y","Z","ZH"]
PHONEME_TO_ID = {p: i for i, p in enumerate(PHONEMES)}

def process_single_doc(doc_data):
    """
    Pure CPU-bound function. No DB logic here.
    doc_data is a tuple: (id, searchable_text)
    """
    doc_id, text_content = doc_data
    if not text_content:
        return None
    
    # Tokenize (faster than regex in some cases, but keeping your logic simplified)
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
        return None

    # Generate Trigrams
    trigram_ids = list(set([
        phoneme_ints[i]*1600 + phoneme_ints[i+1]*40 + phoneme_ints[i+2]
        for i in range(len(phoneme_ints)-2)
    ]))

    return {
        "doc": {"document_id": doc_id, "phonemes": bytes(phoneme_ints), "phoneme_length": len(phoneme_ints)},
        "trigrams": [{"trigram_id": t, "document_id": doc_id} for t in trigram_ids]
    }




def process_single_doc(doc_data):
    # doc_data is now a raw dictionary of the database row
    doc_id = doc_data['id']
    
    # --- RECONSTRUCT SEARCHABLE TEXT HERE ---
    # Replace 'title', 'artist', etc. with your actual column names
    text_content = f"{doc_data.get('title', '')} {doc_data.get('lyrics', '')}" 
    # ----------------------------------------

    if not text_content:
        return None
    
    # (Rest of your phoneme logic remains the same)
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
        return None

    trigram_ids = list(set([
        phoneme_ints[i]*1600 + phoneme_ints[i+1]*40 + phoneme_ints[i+2]
        for i in range(len(phoneme_ints)-2)
    ]))

    return {
        "doc": {"document_id": doc_id, "phonemes": bytes(phoneme_ints), "phoneme_length": len(phoneme_ints)},
        "trigrams": [{"trigram_id": t, "document_id": doc_id} for t in trigram_ids]
    }

def index_phonemes(engine, batch_size=5000): # Increased batch size for speed
    num_workers = mp.cpu_count()
    
    # 1. Open a raw connection
    with engine.connect() as conn:
        # 2. Fetch all raw data from the documents table
        # Using Document.__table__ avoids the "Property" error
        query = select(Document.__table__)
        result_proxy = conn.execute(query)
        
        with ProcessPoolExecutor(max_workers=num_workers) as executor:
            pbar = tqdm(desc="Indexing")
            it = iter(result_proxy)

            while True:
                # 3. Get a batch of rows and convert to dictionaries immediately
                # This makes them safe to send to other processes
                chunk = [row._asdict() for row in islice(it, batch_size)]
                if not chunk:
                    break
                
                # 4. Process in parallel
                results = list(executor.map(process_single_doc, chunk))
                
                doc_inserts = []
                trigram_inserts = []
                for res in results:
                    if res:
                        doc_inserts.append(res['doc'])
                        trigram_inserts.extend(res['trigrams'])
                
                # 5. Fast Bulk Insert
                if doc_inserts:
                    with engine.begin() as write_conn:
                        write_conn.execute(insert(PhonemeDocument), doc_inserts)
                        if trigram_inserts:
                            write_conn.execute(insert(PhonemeTrigram), trigram_inserts)
                
                pbar.update(len(chunk))

def main():
    DB_URL = DB_URL = "sqlite:///songs.db" 

    engine = create_engine(DB_URL, 
                           pool_size=20, 
                           max_overflow=0,
                           # Increase execution speed
                           execution_options={"stream_results": True})
    print("Cleaning up old index data...")
    PhonemeBase.metadata.drop_all(engine) # This deletes the phoneme tables
    # -----------------------

    PhonemeBase.metadata.create_all(engine) # This recreates them empty

    
    print("Starting optimized indexing...")
    index_phonemes(engine)
    print("Indexing complete.")

if __name__ == "__main__":
    # Windows fix for multiprocessing
    mp.freeze_support()
    print("Running phoneme indexing pipeline...")
    main()