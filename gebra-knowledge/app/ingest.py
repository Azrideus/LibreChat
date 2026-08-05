import os
import glob
import hashlib
from sqlalchemy import create_engine, text
from sqlalchemy.exc import ProgrammingError
from langchain_community.document_loaders import (
    TextLoader, UnstructuredMarkdownLoader, Docx2txtLoader
)
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_postgres import PGVector
from lib.PyMuPDF4LLMLoader import PyMuPDF4LLMLoader
from lib.categories import CATEGORIES
from lib.embeddings import build_embeddings
from lib.config import DOCS_DIR, CONNECTION_STRING

LOADERS = {
    ".pdf": PyMuPDF4LLMLoader,
    ".md": UnstructuredMarkdownLoader,
    ".txt": TextLoader,
    ".docx": Docx2txtLoader,
}


def hash_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def discover_files(category_dir):
    files = {}
    for path in glob.glob(f"{category_dir}/**/*", recursive=True):
        ext = os.path.splitext(path)[1].lower()
        if ext not in LOADERS or os.path.isdir(path):
            continue
        files[path] = hash_file(path)
    return files


def get_indexed_hashes(vectorstore):
    """Map of source path -> file_hash already stored in the collection."""
    with vectorstore._make_sync_session() as session:
        collection = vectorstore.get_collection(session)
        if collection is None:
            return {}
        rows = session.query(
            vectorstore.EmbeddingStore.cmetadata["source"].astext,
            vectorstore.EmbeddingStore.cmetadata["file_hash"].astext,
        ).filter(
            vectorstore.EmbeddingStore.collection_id == collection.uuid
        ).distinct().all()
    return {source: file_hash for source, file_hash in rows}


def delete_sources(vectorstore, sources):
    if not sources:
        return
    with vectorstore._make_sync_session() as session:
        collection = vectorstore.get_collection(session)
        if collection is None:
            return
        session.query(vectorstore.EmbeddingStore).filter(
            vectorstore.EmbeddingStore.collection_id == collection.uuid,
            vectorstore.EmbeddingStore.cmetadata["source"].astext.in_(sources),
        ).delete(synchronize_session=False)
        session.commit()


def count_rows(vectorstore):
    with vectorstore._make_sync_session() as session:
        collection = vectorstore.get_collection(session)
        if collection is None:
            return 0
        return session.query(vectorstore.EmbeddingStore).filter(
            vectorstore.EmbeddingStore.collection_id == collection.uuid
        ).count()


def load_and_split(path, file_hash, splitter):
    ext = os.path.splitext(path)[1].lower()
    loader_cls = LOADERS[ext]
    print(f"----")
    print(f"File: {path}")
    print(f" → Loading...")
    docs = loader_cls(path).load()
    for doc in docs:
        doc.metadata["source"] = path
        doc.metadata["file_hash"] = file_hash
    chunks = splitter.split_documents(docs)
    print(f" Split into {len(chunks)} chunks")
    print(f"----")
    return chunks

# ---------------------------------------------------------------------------- #


def ingest_category(category, embeddings, splitter):
    print(f"\n=== Category: {category['key']} ({category['collection']}) ===")
    category_dir = os.path.join(DOCS_DIR, category["folder"])
    if not os.path.isdir(category_dir):
        print(f"⚠️  Folder {category_dir} does not exist, skipping.")
        return

    vectorstore = PGVector(
        embeddings=embeddings,
        collection_name=category["collection"],
        connection=CONNECTION_STRING,
        use_jsonb=True,
    )

    current_files = discover_files(category_dir)
    indexed_hashes = get_indexed_hashes(vectorstore)

    changed_paths = [
        path for path, file_hash in current_files.items()
        if indexed_hashes.get(path) != file_hash
    ]
    removed_paths = [
        path for path in indexed_hashes
        if path not in current_files
    ]

    print(
        f"ℹ️  Found {len(current_files)} docs "
        f"({len(changed_paths)} new/changed, "
        f"{len(current_files) - len(changed_paths)} unchanged, "
        f"{len(removed_paths)} removed)"
    )

    stale_sources = set(changed_paths) | set(removed_paths)
    if stale_sources:
        print(
            f"🗑️  Deleting {len(stale_sources)} stale sources from the vector store...")
        delete_sources(vectorstore, stale_sources)
        print("✅ Done deleting stale sources.")

    if not changed_paths:
        print("Nothing to re-index.")
        print(
            f"📊 Collection '{category['collection']}' now has {count_rows(vectorstore)} rows")
        return

    print("🧭 Indexing new/changed files into the vector store...")
    chunks = []
    for path in changed_paths:
        chunks.extend(load_and_split(path, current_files[path], splitter))

    print(f"✅ Split into {len(chunks)} chunks")
    print(f"Adding into vector store...")
    vectorstore.add_documents(chunks)
    print(f"✅ Indexed {len(chunks)} chunks for {len(changed_paths)} file(s)")
    print(
        f"📊 Collection '{category['collection']}' now has {count_rows(vectorstore)} rows")


def get_existing_collection_names(engine):
    with engine.connect() as conn:
        try:
            rows = conn.execute(
                text("SELECT name FROM langchain_pg_collection")
            ).all()
        except ProgrammingError:
            return set()
    return {row[0] for row in rows}


def prune_orphaned_collections(engine, embeddings, known_collections):
    """Drop collections left behind by categories renamed/removed from categories.py."""
    orphaned = get_existing_collection_names(engine) - known_collections
    if not orphaned:
        return

    print(f"\n=== Pruning orphaned collections ===")
    print(f"⚠️  Found {len(orphaned)} collection(s) with no matching category: "
          f"{sorted(orphaned)}")
    for name in sorted(orphaned):
        vectorstore = PGVector(
            embeddings=embeddings,
            collection_name=name,
            connection=CONNECTION_STRING,
            use_jsonb=True,
        )
        rows = count_rows(vectorstore)
        vectorstore.delete_collection()
        print(f"🗑️ Dropped orphaned collection '{name}' ({rows} rows)")


def main():
    embeddings = build_embeddings()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1500, chunk_overlap=100)

    for category in CATEGORIES:
        ingest_category(category, embeddings, splitter)

    engine = create_engine(CONNECTION_STRING)
    known_collections = {category["collection"] for category in CATEGORIES}
    prune_orphaned_collections(engine, embeddings, known_collections)
    engine.dispose()


if __name__ == "__main__":
    main()
    os._exit(0)
