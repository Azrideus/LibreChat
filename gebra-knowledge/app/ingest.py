import os
import glob
from langchain_community.document_loaders import (
    PyPDFLoader, TextLoader, UnstructuredMarkdownLoader, Docx2txtLoader
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
    "EMBEDDINGS_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)
DOCS_DIR = os.environ.get("DOCS_DIR", "/app/docs")

CONNECTION_STRING = (
    f"postgresql+psycopg://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{POSTGRES_DB}"
)

LOADERS = {
    ".pdf": PyPDFLoader,
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

    splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=100)
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
