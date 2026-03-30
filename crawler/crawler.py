import os
import re
import time
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

GENIUS_API_BASE = "https://api.genius.com"
ACCESS_TOKEN = os.getenv("GENIUS_ACCESS_TOKEN")
HEADERS = {"Authorization": f"Bearer {ACCESS_TOKEN}"}


def search_song(query: str) -> dict | None:
    """Search Genius API and return the first matching song result."""
    response = requests.get(
        f"{GENIUS_API_BASE}/search",
        headers=HEADERS,
        params={"q": query}
    )
    response.raise_for_status()
    hits = response.json()["response"]["hits"]
    songs = [h for h in hits if h["type"] == "song"]
    return songs[0]["result"] if songs else None


def scrape_lyrics(url: str) -> str | None:
    """Scrape lyrics from a Genius song page URL."""
    response = requests.get(url, headers={
        # Mimic a browser to avoid blocks
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
    })
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Lyrics are split across multiple containers with this attribute
    containers = soup.find_all("div", {"data-lyrics-container": "true"})
    if not containers:
        return None

    lyrics_parts = []
    for container in containers:
        # Replace <br> tags with newlines before extracting text
        for br in container.find_all("br"):
            br.replace_with("\n")
        lyrics_parts.append(container.get_text())

    lyrics = "\n".join(lyrics_parts)

    # Clean up excessive blank lines
    lyrics = re.sub(r"\n{3,}", "\n\n", lyrics).strip()
    return lyrics


def get_lyrics(artist: str, song: str) -> str | None:
    """Full pipeline: search → get URL → scrape lyrics."""
    query = f"{artist} {song}"
    print(f"Searching for: {query}")

    result = search_song(query)
    if not result:
        print("No results found.")
        return None

    print(f"Found: {result['full_title']} — {result['url']}")
    time.sleep(1)  # Be polite to the server

    return scrape_lyrics(result["url"])


def crawl_songs(songs: list[tuple[str, str]], output_dir: str = "lyrics") -> None:
    """Crawl a list of (artist, song) tuples and save to .txt files."""
    os.makedirs(output_dir, exist_ok=True)

    for artist, song in songs:
        lyrics = get_lyrics(artist, song)
        if lyrics:
            filename = re.sub(r"[^\w\s-]", "", f"{artist}_{song}").replace(" ", "_")
            filepath = os.path.join(output_dir, f"{filename}.txt")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(lyrics)
            print(f"Saved: {filepath}")
        else:
            print(f"Could not retrieve lyrics for {artist} - {song}")

        time.sleep(2)  # Rate limit: avoid hammering the server


if __name__ == "__main__":
    songs_to_crawl = [
        ("Post Malone", "Sunflower"),
        ("Kendrick Lamar", "HUMBLE"),
        ("Arctic Monkeys", "Do I Wanna Know"),
    ]
    crawl_songs(songs_to_crawl)
