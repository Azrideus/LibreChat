from typing import List

from langchain_huggingface import HuggingFaceEmbeddings

from lib.config import EMBEDDINGS_MODEL, E5_PREFIX_MARKERS


class PrefixedHuggingFaceEmbeddings(HuggingFaceEmbeddings):
    """HuggingFaceEmbeddings that applies the e5 query/passage prefix convention."""

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return super().embed_documents([f"passage: {text}" for text in texts])

    def embed_query(self, text: str) -> List[float]:
        return super().embed_query(f"query: {text}")


def build_embeddings() -> HuggingFaceEmbeddings:
    """Single source of truth for embeddings, shared by ingest and search.

    Ingest (passage prefix) and search (query prefix) must use the exact same
    model + prefixing scheme, or the two ends of the vector space drift apart.
    """
    model_name_lower = EMBEDDINGS_MODEL.lower()
    if any(marker in model_name_lower for marker in E5_PREFIX_MARKERS):
        return PrefixedHuggingFaceEmbeddings(model_name=EMBEDDINGS_MODEL)
    return HuggingFaceEmbeddings(model_name=EMBEDDINGS_MODEL)
