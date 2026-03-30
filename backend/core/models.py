from dataclasses import dataclass, field
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, Text


class Base(DeclarativeBase):
    pass


class Document(Base):
    """
    Represents a song document from the lyrics CSV.
    SQLAlchemy ORM model.
    """
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, default="")
    content: Mapped[str] = mapped_column(Text, default="")  # lyrics
    artist: Mapped[str] = mapped_column(String, default="")
    tag: Mapped[str] = mapped_column(String, default="")
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    features: Mapped[str] = mapped_column(String, default="")
    language: Mapped[str] = mapped_column(String, default="")
    language_cld3: Mapped[str] = mapped_column(String, default="")
    language_ft: Mapped[str] = mapped_column(String, default="")

    # Populated during indexing (transient, not in DB)
    tokens: list[str] = field(default_factory=list, init=False)

    def __post_init__(self):
        # Allow tokens to be set after init if needed, though usually set by tokenizer
        self.tokens = []

    @property
    def searchable_text(self) -> str:
        """Text that gets tokenized and indexed."""
        parts = [self.title, self.artist, self.content]
        return " ".join(p for p in parts if p)

    def short_lyrics(self, max_len: int = 120) -> str:
        """First N characters of lyrics for display."""
        if not self.content:
            return ""
        cleaned = " ".join(self.content.split())
        if len(cleaned) <= max_len:
            return cleaned
        return cleaned[:max_len].rsplit(" ", 1)[0] + "..."


@dataclass
class SearchResult:
    document: Document
    score: float
    proximity_score: float = 0.0
    phrase_matched: bool = False