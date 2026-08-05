import contextlib

import uvicorn
from starlette.applications import Starlette
from starlette.routing import Mount
from mcp.server.fastmcp import FastMCP
from langchain_postgres import PGVector
from lib.categories import CATEGORIES
from lib.embeddings import build_embeddings
from lib.config import (
    CONNECTION_STRING,
    MIN_TOP_K,
    MAX_TOP_K,
    DEFAULT_TOP_K,
    MMR_FETCH_MULTIPLIER,
)

embeddings = build_embeddings()


def make_search_tool(category, vectorstore):
    def search(query: str, top_k: int = DEFAULT_TOP_K) -> str:
        top_k = max(MIN_TOP_K, min(top_k, MAX_TOP_K))
        results = vectorstore.max_marginal_relevance_search_with_score_by_vector(
            embeddings.embed_query(query),
            k=top_k,
            fetch_k=top_k * MMR_FETCH_MULTIPLIER,
        )
        if not results:
            with vectorstore._make_sync_session() as session:
                collection = vectorstore.get_collection(session)
                total_rows = session.query(vectorstore.EmbeddingStore).filter(
                    vectorstore.EmbeddingStore.collection_id == collection.uuid
                ).count()
            return (
                f"No relevant results found in the '{category['key']}' "
                f"knowledge base (searched {total_rows} rows)."
            )

        blocks = []
        for doc, score in results:
            source = doc.metadata.get("source", "unknown")
            blocks.append(
                f"[source: {source} | score: {score:.4f}]\n{doc.page_content}")
        return "\n\n---\n\n".join(blocks)

    search.__name__ = category["tool_name"]
    search.__doc__ = category["description"]
    return search


def build_server(category: dict) -> FastMCP:
    """One FastMCP instance per category, each carrying exactly one tool.

    Mounted at its own path below, so LibreChat sees it as its own MCP
    server and users can toggle it independently in the chat MCP dropdown.
    """
    vectorstore = PGVector(
        embeddings=embeddings,
        collection_name=category["collection"],
        connection=CONNECTION_STRING,
        use_jsonb=True,
    )
    # host="0.0.0.0" (not 127.0.0.1/localhost, FastMCP's default) keeps FastMCP
    # from auto-enabling Host-header DNS-rebinding protection, which would
    # otherwise reject requests arriving with Host: gebra-knowledge-mcp:8000
    # from other containers on the Docker network.
    server = FastMCP(
        f"gebra-{category['key']}", stateless_http=True, host="0.0.0.0", port=8000)
    server.tool(name=category["tool_name"], description=category["description"])(
        make_search_tool(category, vectorstore)
    )
    return server


servers = {category["key"]: build_server(category) for category in CATEGORIES}


@contextlib.asynccontextmanager
async def lifespan(app):
    async with contextlib.AsyncExitStack() as stack:
        for server in servers.values():
            await stack.enter_async_context(server.session_manager.run())
        yield


# Each category is reachable at http://<host>:8000/<key>/mcp, e.g.
# .../datasheets/mcp, .../medical_datasheets/mcp, .../math/mcp, .../codding/mcp, .../general/mcp
app = Starlette(
    routes=[
        Mount(f"/{key}", app=server.streamable_http_app())
        for key, server in servers.items()
    ],
    lifespan=lifespan,
)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
