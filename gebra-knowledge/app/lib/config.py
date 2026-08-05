"""Single source of truth for constants shared across the gebra-knowledge app
(ingest.py, mcp_server.py, search_test.py, embeddings.py, categories.py).
"""

import os

DB_HOST = os.environ["DB_HOST"]
DB_PORT = os.environ.get("DB_PORT", "5432")
POSTGRES_DB = os.environ["POSTGRES_DB"]
POSTGRES_USER = os.environ["POSTGRES_USER"]
POSTGRES_PASSWORD = os.environ["POSTGRES_PASSWORD"]
DOCS_DIR = os.environ.get("DOCS_DIR", "/app/docs")

CONNECTION_STRING = (
    f"postgresql+psycopg://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{POSTGRES_DB}"
)

EMBEDDINGS_MODEL = os.environ.get(
    "EMBEDDINGS_MODEL", "intfloat/multilingual-e5-small"
)

# E5-family models (intfloat/e5-*, intfloat/multilingual-e5-*) are trained on
# asymmetric "query: " / "passage: " prefixed pairs. HuggingFaceEmbeddings does not
# add these automatically (that only happens for the BGE/Instructor embedding
# classes), so leaving it off means every query and every chunk is embedded the
# way the model was never optimized for — a direct, measurable hit to relevance,
# independent of chunking or top_k. See:
# https://huggingface.co/intfloat/multilingual-e5-small#faq
E5_PREFIX_MARKERS = ("e5-", "/e5", "multilingual-e5")

MIN_TOP_K = 5
MAX_TOP_K = 20
DEFAULT_TOP_K = 10
# Candidate pool MMR diversifies over, as a multiple of top_k. Plain similarity
# search returns the top_k nearest chunks, which for a single PDF are often
# near-duplicate slices of the same paragraph; MMR trades a bit of pure relevance
# for topic coverage across the whole result set.
MMR_FETCH_MULTIPLIER = 4

# Appended to every category description in categories.py. Vector search only ever
# returns chunks that are close to the exact wording of a single query, so one
# narrow call with a low top_k systematically under-serves broad questions ("tell
# me about X", "give an example"). Spelling this out in the tool description is
# what actually changes model behavior for non-agent conversations, where there is
# no separate planning step forcing multiple retrieval rounds.
SEARCH_STRATEGY_SUFFIX = (
    " Query strategy: this is plain vector similarity search, not a general Q&A "
    "engine — results are only as good as the query. For broad or multi-part "
    "questions, call this tool several times with different, specific queries "
    "(e.g. one for the core concept, one per sub-topic or keyword the user "
    "mentioned, one for 'example'/'usage' phrasing) rather than one vague query, "
    "and always include the key proper nouns/product/library names verbatim. Use "
    "top_k 3-5 for a narrow lookup (a specific part number, a single API call) and "
    "top_k 10-15 for broad or 'overview'/'explain'/'example' requests. Combine "
    "results across calls before answering."
)
