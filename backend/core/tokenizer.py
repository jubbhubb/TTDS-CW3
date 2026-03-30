import re
import Stemmer
import nltk
import re
import Stemmer
from num2words import num2words
from itertools import chain
from nltk.corpus import stopwords



class Tokenizer:
    """Tokenizes and normalizes text into searchable terms."""

    def __init__(self, stop_words: set[str] | None = None):
        self.stop_words = stop_words or {
            "what", "which", "who", "whom", "this", "that", "these", "those", "am", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "having", "do", "does", "did", "doing", "a", "an", "the", "and", "but", "if", "or", "because", "as", "until", "while", "of", "at", "by", "for", "with", "about", "against", "between", "into", "through", "during", "before", "after", "above", "below", "to", "from", "up", "down", "in", "out", "on", "off", "over", "under", "again", "further", "then", "once", "here", "there", "when", "where", "why", "how", "all", "any", "both", "each", "few", "more", "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very", "s", "t", "can", "will", "just", "don", "should", "now"
        }
        self.porter_stemmer = Stemmer.Stemmer('porter')
        self.spanishStemmer = Stemmer.Stemmer('spanish')
        nltk.download('stopwords', quiet=True)
        self.stop_words_spanish = set(stopwords.words('spanish'))





    def split_and_normalise(self, token, isSpanish : bool = False):

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
            try:
                if "." in number_str:
                    return num2words(float(number_str))
                else:
                    return num2words(int(number_str))
            except (ValueError, IndexError, AssertionError):
                return number_str

        token = re.sub(r"\d+(\.\d+)?", replace_number, token)
        return token



    def tokenize(self, text: str, use_normalize: bool =True, for_spanish: bool =False, use_stemming: bool = True, use_stopping: bool = True) -> list[str]:
        tokens = []
        if use_normalize:
            text = text.lower()
            text = text.split()
            for word in text:
                if re.search(r"\d", word):
                    word = self.split_and_normalise(word)
                word = re.sub(r"[^\w\s]", " ", word)
                words = word.split()
                for word2 in words:
                    if not word2:
                        continue
                    if use_stopping and word2.lower() in (self.stop_words_spanish if for_spanish else self.stop_words):
                        continue
                    if use_stemming:
                        if for_spanish:
                            stemmed_word = self.spanishStemmer.stemWord(word2)
                        else:
                            stemmed_word = self.porter_stemmer.stemWord(word2)
                    else :
                        stemmed_word = word2
                    tokens.append(stemmed_word)
        else:
            text = re.sub(r'\[.*?\]', '', text)
            for word in re.split(r'[^A-Za-z0-9]+', text):
                if not word:
                    continue

                # Apply stopword removal
                if use_stopping and word.lower() in (self.stop_words_spanish if for_spanish else self.stop_words):
                    continue
                # Convert to lowercase
                word = word.lower()

                # Apply stemming
                if use_stemming:
                    if for_spanish:
                        stemmed_word = self.spanishStemmer.stemWord(word)
                    else:
                        stemmed_word = self.porter_stemmer.stemWord(word)
                else:
                    stemmed_word = word

                tokens.append(stemmed_word)

        return tokens

    def tokenize_with_positions(self, text: str, use_stemming: bool = True, use_stopping: bool = True) -> list[tuple[str, int]]:
        """
        Returns (token, original_position) pairs.
        Useful for highlighting and debugging.
        """
        text = text.lower()
        words = re.findall(r"[a-z0-9]+", text)
        result = []
        for i, w in enumerate(words):
            if w not in self.stop_words:
                result.append((w, i))
        return result

    def tokenize_keep_stops(self, text: str) -> list[str]:
        """Tokenize but keep stop words. Used for phrase queries."""
        text = text.lower()
        return re.findall(r"[a-z0-9]+", text)

    def is_stop_word(self, token: str) -> bool:
        return token in self.stop_words


