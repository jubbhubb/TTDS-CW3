
import re
from num2words import num2words
from core.tokenizer import Tokenizer


def split_and_normalise( token, isSpanish : bool = False):

    CURRENCY_MAP = {
        "£": "GBP",
        "$": "USD",
        "€": "EUR"
    }

    token = token.replace(",", "").replace("'", "")

    match = re.match(r"^([£$€])(\d+(\.\d+)?)$", token)
    if match:
        symbol = match.group(1)
        number = float(match.group(2)) * 100  # convert to cents/pence
        if number.is_integer():
            number = int(number)
        if isSpanish:
            number_in_words = num2words(number, to='currency', currency=CURRENCY_MAP[symbol], lang='es')
        else:
            number_in_words = num2words(number, to='currency', currency=CURRENCY_MAP[symbol])

        # Optional: remove "zero" parts (existing logic)
        if "zero" in number_in_words:
            parts = [p for p in number_in_words.split(",") if "zero" not in p]
            number_in_words = ", ".join(parts)

        return number_in_words


    def replace_ordinal(match):
        number = int(match.group(1))
        return num2words(number, to='ordinal')

    token = re.sub(r"(\d+)(st|nd|rd|th)", replace_ordinal, token)


    def replace_decade(match):
        number = int(match.group(1))
        if 10 <= number <= 99:
            word = num2words(number)
            word = word[:-1] + "ies" if word.endswith("y") else word + "s"
            return word
        return num2words(number, to='year') + "s"  # 1990s → nineteen nineties

    token = re.sub(r"(\d{2,4})s", replace_decade, token)


    def replace_percent(match):
        number = int(match.group(1))
        return num2words(number) + " percent"

    token = re.sub(r"(\d+)%", replace_percent, token)

    def replace_number(match):
        number_str = match.group()
        if "." in number_str:
            # convert to float for proper decimal handling
            number_float = float(number_str)
            return num2words(number_float)  # num2words handles 'point' correctly
        else:
            return num2words(int(number_str))
    token = re.sub(r"\d+(\.\d+)?", replace_number, token)
    return token


def find_lyric_from_position(position: int, document, tokenizer, use_normalize: bool = True, for_spanish: bool = False) -> str | None:
    """
    Finds the lyric snippet by mimicking the IngestionPipeline's tokenization.
    
    :param position: The word index from the search result.
    :param document: The document object (must have .title and .content).
    :param tokenizer: The same Tokenizer instance used in IngestionPipeline.
    :param for_spanish: Boolean indicating if Spanish rules should apply.
    """
    word_counter = 0
    
    # 1. Mirror the IngestionPipeline construction: Title + Content
    # We treat the title as the first "line".
    title = getattr(document, 'title', '')
    lyrics = getattr(document, 'content', '')
    
    # Create the line list (Title is index 0)
    lines = [title] + lyrics.split('\n')

    for index, line in enumerate(lines):
        # 2. Use the ACTUAL tokenizer to count words in this line.
        # This automatically handles stop words, punctuation, and [Metadata] 
        # exactly the same way the search index did.
        line_tokens = tokenizer.tokenize(line, for_spanish=for_spanish)
        line_word_count = len(line_tokens)

        # 3. Check if the target position falls within this line
        if word_counter <= position < word_counter + line_word_count:
            
            # --- Found the line! Now gather context (Previous, Current, Next) ---
            
            # Identify the range for the snippet
            # We look for the closest lines that actually contain text
            
            current_line = lines[index]
            
            # Find the first non-empty line above
            prev_line = ""
            for i in range(index - 1, -1, -1):
                if lines[i].strip():
                    prev_line = lines[i]
                    break
            
            # Find the first non-empty line below
            next_line = ""
            for i in range(index + 1, len(lines)):
                if lines[i].strip():
                    next_line = lines[i]
                    break

            # Combine and return (filtering out empty context if at start/end)
            snippet = [l.strip() for l in [prev_line, current_line, next_line] if l.strip()]
            return '\n'.join(snippet)

        # 4. Increment the counter by the number of tokens found in this line
        word_counter += line_word_count

    return None

# def find_lyric_from_position(position, document, stop_words, use_normalize=True) -> str | None:
    '''
    Given a document and a word position, find the lyric snippet.
    Ignores empty lines and metadata lines like [Chorus].
    '''
    word_counter = 0
    title = getattr(document, 'title', '') 
    

    lyrics = document.content
    print(f"[DEBUG] Finding lyric snippet for position {position} in document ID {document.id}")
    print(f"[DEBUG] Document content starts with: {lyrics[:100]}...")  # Show the start of the lyrics for context
    lines = [title] + lyrics.split('\n')

    def is_valid_content(l):
        """Returns True if the line is actual lyric text."""
        clean = l.strip()
        if not clean:
            return False
        # Matches lines that start with [ and end with ] (ignoring internal spaces)
        if re.match(r'^\[.*\]$', clean):
            return False
        return True

    # We only want to iterate over and count words in VALID lines
    for index, line in enumerate(lines):
        if not is_valid_content(line):
            continue  # Skip empty or [Metadata] lines entirely

        # Calculate words in this valid line
        words_in_line = []
        if use_normalize:
            # Replicate your exact indexing normalization
            for word in line.lower().split():
                if re.search(r"\d", word):
                    # Note: Ensure split_and_normalise is accessible in this scope
                    word = split_and_normalise(word)
                
                word = re.sub(r"[^\w\s]", " ", word)
                for word2 in word.split():
                    if word2 and word2.lower() not in stop_words:
                        words_in_line.append(word2)
        else:
            # Replicate your standard split
            line_clean = re.sub(r'\[.*?\]', '', line)
            words_in_line = [w for w in re.split(r'[^A-Za-z0-9]+', line_clean) 
                             if w and w.lower() not in stop_words]

        line_word_count = len(words_in_line)

        print(f"[DEBUG] Line {index}: '{line}' has {line_word_count} valid words. Word counter: {word_counter}")
        print(f"[DEBUG] Words in line: {words_in_line}")

        # Check if target 'position' is within this specific line
        if word_counter <= position < word_counter + line_word_count:
            # Found the line! Now find the context around it.
            
            # 1. Find the first valid line ABOVE
            prev_line = ""
            for i in range(index - 1, -1, -1):
                if is_valid_content(lines[i]):
                    prev_line = lines[i]
                    break
            
            # 2. The current line
            current_line = lines[index]

            # 3. Find the first valid line BELOW
            next_line = ""
            for i in range(index + 1, len(lines)):
                if is_valid_content(lines[i]):
                    next_line = lines[i]
                    break

            # Combine them, filtering out empty strings if at the start/end of song
            snippet = [l for l in [prev_line, current_line, next_line] if l]
            return '\n'.join(snippet)

        word_counter += line_word_count

    return None

# no need to change this because all songs are stored in same database
def build_results(tuples, repository, stop_words) -> list[dict]:
    print("[DEBUG] Building results from tuples:", tuples)
    results = []
    for (doc_id, position) in tuples:
        print(f"[DEBUG] Processing doc_id: {doc_id}, position: {position}")
        if position is None:
            print(f"Position is None for doc_id {doc_id}, skipping lyric snippet extraction.")
            continue
        doc = repository.get(doc_id)
        if doc:
            if getattr(doc, 'language', None) == 'es':
                print(f"[DEBUG] Document ID {doc_id} is in Spanish. Using Spanish stop words.")
                use_spanish = True
            else:
                print(f"[DEBUG] Document ID {doc_id} is in English. Using English stop words.")
                use_spanish = False
                tokenizer = Tokenizer()  
            lyrics = find_lyric_from_position(position, doc, tokenizer, use_normalize=True, for_spanish=use_spanish)
            print(f"[DEBUG] Found lyric snippet for doc_id {doc_id}: {lyrics}")
            if lyrics:
                results.append({
                    "id": doc_id,                
                    "title": doc.title,
                    "artist": doc.artist,
                    "year": doc.year,
                    "lyric_snippet": lyrics,     
                    "tag": getattr(doc, 'tag', ''),
                    "views": getattr(doc, 'views', 0),
                    "features": getattr(doc, 'features', ''),
                    "language": getattr(doc, 'language', '')
                })
            else:
                print(f"Lyric snippet not found in song ID {doc_id}.")
        else:
            print(f"Song ID {doc_id} not found.")
    return results