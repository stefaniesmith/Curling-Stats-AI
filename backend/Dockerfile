FROM python:3.13-slim

WORKDIR /app

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

RUN pip install --no-cache-dir uv==0.11.29

COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend/alembic.ini ./
COPY backend/scripts ./scripts
COPY backend/src ./src
COPY backend/docker ./docker
RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["sh", "/app/docker/start-api.sh"]
