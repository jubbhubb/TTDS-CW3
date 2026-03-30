from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import LargeBinary, Integer, String
from sqlalchemy import ForeignKey

class PhonemeBase(DeclarativeBase):
    pass

class PhonemeDocument(PhonemeBase):
    __tablename__ = "phoneme_documents"

    document_id: Mapped[str] = mapped_column(String, primary_key=True)
    phonemes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    phoneme_length: Mapped[int] = mapped_column(Integer, nullable=False)

class PhonemeTrigram(PhonemeBase):
    __tablename__ = "phoneme_trigrams"

    trigram_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("phoneme_documents.document_id"),
        primary_key=True
    )
