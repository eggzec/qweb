FROM astral/uv:python3.13-bookworm-slim

WORKDIR /app

COPY pyproject.toml pyproject.toml
COPY .python-version .python-version
COPY src/ src/
RUN uv sync --no-dev --no-cache

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
