import os
import glob
import pymupdf4llm
from langchain_core.documents import Document
from langchain_community.document_loaders import (
    TextLoader, UnstructuredMarkdownLoader, Docx2txtLoader
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_postgres import PGVector

DB_HOST = os.environ["DB_HOST"]
DB_PORT = os.environ.get("DB_PORT", "5432")
POSTGRES_DB = os.environ["POSTGRES_DB"]
POSTGRES_USER = os.environ["POSTGRES_USER"]
POSTGRES_PASSWORD = os.environ["POSTGRES_PASSWORD"]
COLLECTION_NAME = os.environ.get("COLLECTION_NAME", "global_knowledge")
EMBEDDINGS_MODEL = os.environ.get(
    "EMBEDDINGS_MODEL", "BAAI/bge-m3"
)
DOCS_DIR = os.environ.get("DOCS_DIR", "/app/docs")

CONNECTION_STRING = (
    f"postgresql+psycopg://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{POSTGRES_DB}"
)


class PyMuPDF4LLMLoader:
    """Drop-in replacement for PyPDFLoader with the same `.load()`
    interface, using pymupdf4llm's markdown-aware extraction for
    better table/heading fidelity."""

    def __init__(self, file_path):
        self.file_path = file_path

    def load(self):
        md_pages = pymupdf4llm.to_markdown(self.file_path, page_chunks=True)

        docs = []
        for i, page_data in enumerate(md_pages, start=1):
            text = page_data.get("text", "")
            if not text:
                continue
            docs.append(
                Document(
                    page_content=text,
                    metadata={"source": self.file_path, "page": i},
                )
            )
        return docs


LOADERS = {
    ".pdf": PyMuPDF4LLMLoader,
    ".md": UnstructuredMarkdownLoader,
    ".txt": TextLoader,
    ".docx": Docx2txtLoader,
}


def load_documents():
    docs = []
    for path in glob.glob(f"{DOCS_DIR}/**/*", recursive=True):
        ext = os.path.splitext(path)[1].lower()
        loader_cls = LOADERS.get(ext)
        if not loader_cls or os.path.isdir(path):
            continue
        print(f"Loading {path}")
        docs.extend(loader_cls(path).load())
    return docs


def main():
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDINGS_MODEL)

    vectorstore = PGVector(
        embeddings=embeddings,
        collection_name=COLLECTION_NAME,
        connection=CONNECTION_STRING,
        use_jsonb=True,
    )

    raw_docs = load_documents()
    print(f"Loaded {len(raw_docs)} raw documents")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1500, chunk_overlap=100)
    chunks = splitter.split_documents(raw_docs)
    print(f"Split into {len(chunks)} chunks")

    # Wipe and re-add for a clean re-index each run.
    # Comment this out if you'd rather append incrementally.
    vectorstore.delete_collection()
    vectorstore.create_collection()

    vectorstore.add_documents(chunks)
    print(f"Indexed {len(chunks)} chunks into collection '{COLLECTION_NAME}'")


if __name__ == "__main__":
    main()
