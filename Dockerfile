FROM python:3.12-slim

WORKDIR /app

COPY . .
RUN pip install -e .

EXPOSE 8420 8888

# Default: HTTP API server
CMD ["python", "-m", "vibe_memory.http_server", "--host", "0.0.0.0", "--port", "8420"]

# For MCP server, override CMD:
# docker run -it vibe-memory python -m vibe_memory.mcp_server