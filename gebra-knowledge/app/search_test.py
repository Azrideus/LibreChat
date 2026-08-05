import sys
import os
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_postgres import PGVector
from categories import CATEGORIES, CATEGORIES_BY_KEY

DB_HOST = os.environ["DB_HOST"]
DB_PORT = os.environ.get("DB_PORT", "5432")
POSTGRES_DB = os.environ["POSTGRES_DB"]
POSTGRES_USER = os.environ["POSTGRES_USER"]
POSTGRES_PASSWORD = os.environ["POSTGRES_PASSWORD"]
EMBEDDINGS_MODEL = os.environ.get(
    "EMBEDDINGS_MODEL", "intfloat/multilingual-e5-small"
)

CONNECTION_STRING = (
    f"postgresql+psycopg://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{POSTGRES_DB}"
)

category_key = sys.argv[1] if len(sys.argv) > 1 else "manuals"
query = sys.argv[2] if len(sys.argv) > 2 else "What is a FreeRTOS queue?"

if category_key not in CATEGORIES_BY_KEY:
    valid = ", ".join(c["key"] for c in CATEGORIES)
    raise SystemExit(f"Unknown category '{category_key}'. Valid categories: {valid}")

category = CATEGORIES_BY_KEY[category_key]

embeddings = HuggingFaceEmbeddings(model_name=EMBEDDINGS_MODEL)
vectorstore = PGVector(
    embeddings=embeddings,
    collection_name=category["collection"],
    connection=CONNECTION_STRING,
    use_jsonb=True,
)

results = vectorstore.similarity_search_with_score(query, k=3)
for doc, score in results:
    print(f"score={score:.4f} source={doc.metadata.get('source')}")
    print(doc.page_content[:400])
    print("---")
