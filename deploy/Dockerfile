FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY ai4ra_mcp ./ai4ra_mcp
RUN uv sync --frozen --no-dev
ENV AI4RA_MCP_HOST=0.0.0.0 AI4RA_MCP_PORT=8000
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "ai4ra-mcp"]
