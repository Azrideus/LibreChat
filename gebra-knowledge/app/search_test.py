import sys
import os
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

CONNECTION_STRING = (
    f"postgresql+psycopg://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{POSTGRES_DB}"
)

query = sys.argv[1] if len(sys.argv) > 1 else "What is a FreeRTOS queue?"

embeddings = HuggingFaceEmbeddings(model_name=EMBEDDINGS_MODEL)
vectorstore = PGVector(
    embeddings=embeddings,
    collection_name=COLLECTION_NAME,
    connection=CONNECTION_STRING,
    use_jsonb=True,
)

results = vectorstore.similarity_search_with_score(query, k=3)
for doc, score in results:
    print(f"score={score:.4f} source={doc.metadata.get('source')}")
    print(doc.page_content[:400])
    print("---")
