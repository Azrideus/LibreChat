FROM python:3.11-slim

WORKDIR /app
COPY requirements-mcp.txt requirements-ingest.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements-mcp.txt -r requirements-ingest.txt

COPY mcp_server.py ingest.py PyMuPDF4LLMLoader.py ./

# FastMCP's streamable-http defaults to port 8000; expose it explicitly
ENV MCP_PORT=8000
EXPOSE 8000

CMD ["python", "mcp_server.py"]
