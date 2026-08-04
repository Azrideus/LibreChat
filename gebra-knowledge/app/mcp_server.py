import os
from mcp.server.fastmcp import FastMCP
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

embeddings = HuggingFaceEmbeddings(model_name=EMBEDDINGS_MODEL)
vectorstore = PGVector(
    embeddings=embeddings,
    collection_name=COLLECTION_NAME,
    connection=CONNECTION_STRING,
    use_jsonb=True,
)

mcp = FastMCP("gebra-knowledge", stateless_http=True,
              host="0.0.0.0", port=8000)


@mcp.tool()
def search_global_knowledge(query: str, top_k: int = 5) -> str:
    """Search the organization's shared knowledge base for information relevant
    to the query. Use this whenever the user asks about internal docs, policies,
    procedures, or any topic that might be covered by company knowledge rather
    than general/public knowledge."""
    results = vectorstore.similarity_search_with_score(query, k=top_k)
    if not results:
        return "No relevant results found in the knowledge base."

    blocks = []
    for doc, score in results:
        source = doc.metadata.get("source", "unknown")
        blocks.append(
            f"[source: {source} | score: {score:.4f}]\n{doc.page_content}")
    return "\n\n---\n\n".join(blocks)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
