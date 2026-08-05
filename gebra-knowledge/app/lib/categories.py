"""Single source of truth for the knowledge-base categories.

Each category maps to:
  - a subfolder under DOCS_DIR that `ingest.py` scans
  - a dedicated PGVector collection that keeps its embeddings isolated
  - an MCP tool that `mcp_server.py` registers so users can pick it individually
    in the LibreChat tool picker

Add a new category here and both ingest.py and mcp_server.py pick it up
automatically — no other code changes needed.
"""

from lib.config import SEARCH_STRATEGY_SUFFIX as _SEARCH_STRATEGY

CATEGORIES = [
    {
        "key": "datasheets",
        "folder": "datasheets",
        "collection": "kb_datasheets",
        "tool_name": "search_datasheets",
        "description": (
            "Search component/chip datasheets (electrical characteristics, pinouts, "
            "register maps, timing diagrams) for products used by GEBRABIT. Use this "
            "when the user asks about a specific part number's specs, registers, "
            "electrical limits, or pin-out." + _SEARCH_STRATEGY
        ),
    },
    {
        "key": "medical_datasheets",
        "folder": "medical_datasheets",
        "collection": "kb_medical_datasheets",
        "tool_name": "search_medical_datasheets",
        "description": (
            "Search medical-device datasheets, technical reference manuals, and "
            "specification sheets for healthcare hardware. Use this when the user "
            "asks about part numbers, operating limits, pinouts, interfaces, or "
            "device-level technical details." + _SEARCH_STRATEGY
        ),
    },
    {
        "key": "math",
        "folder": "math",
        "collection": "kb_math",
        "tool_name": "search_math",
        "description": (
            "Search Math and Physics books, formulas, equations and reference "
            "tables." + _SEARCH_STRATEGY
        ),
    },
    {
        "key": "codding",
        "folder": "codding",
        "collection": "kb_codding",
        "tool_name": "search_codding",
        "description": (
            "Search C/C++ coding reference books, examples, and best practices for "
            "embedded systems and microcontrollers, including FreeRTOS." + _SEARCH_STRATEGY
        ),
    },
    {
        "key": "general",
        "folder": "general",
        "collection": "kb_general",
        "tool_name": "search_general_knowledge",
        "description": (
            "Search general internal knowledge base entries that don't fit datasheets, "
            "application notes, or manuals — policies, procedures, and other internal "
            "notes used by GEBRABIT." + _SEARCH_STRATEGY
        ),
    },
]

CATEGORIES_BY_KEY = {category["key"]: category for category in CATEGORIES}
