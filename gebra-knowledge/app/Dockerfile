FROM python:3.11-slim

WORKDIR /app
COPY requirements-mcp.txt requirements-ingest.txt ./
RUN pip install --no-cache-dir -r requirements-mcp.txt -r requirements-ingest.txt
COPY mcp_server.py ingest.py ./

# FastMCP's streamable-http defaults to port 8000; expose it explicitly
ENV MCP_PORT=8000
EXPOSE 8000

CMD ["python", "mcp_server.py"]
