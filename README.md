# CurlChat

<img src="assets/CurlChatLogo.png" alt="CurlChat logo" width="260" />

CurlChat is a conversational analytics application for exploring Curling Canada player statistics. It combines a FastAPI backend, PostgreSQL analytics data, LangGraph agent orchestration, and a React interface with interactive visualizations.

## Run it locally with Docker

This project is intended to be easy to review and run on a local machine. Docker Compose starts PostgreSQL, the FastAPI application, a production-style Nginx frontend, and Phoenix for optional local tracing. The frontend is available at [http://localhost:5173](http://localhost:5173); its Nginx container serves the Vite production build and proxies both ordinary API requests and streaming responses to the backend.

### Prerequisites

* [Docker Desktop](https://www.docker.com/products/docker-desktop/) (including Docker Compose)
* an OpenAI API key
* Git

The statistics archive remains a separate public repository: [Curling Canada Stats Archive](https://github.com/ccacurling/curling-canada-stats-archive). It is mounted read-only into a one-time importer container; no archive data is copied into this repository or image.

### First run

Clone both repositories, ideally as sibling directories:

```bash
git clone <this-repository-url> Curling-Stats-AI
git clone https://github.com/ccacurling/curling-canada-stats-archive.git curling-canada-stats-archive
cd Curling-Stats-AI
```

Create the local environment file. Set `OPENAI_API_KEY`, and set `ARCHIVE_PATH` to the absolute path of the separate archive checkout.

```bash
cp .env.example .env
```

For example:

```dotenv
OPENAI_API_KEY=your-key
ARCHIVE_PATH=/absolute/path/to/curling-canada-stats-archive
```

Build and start the application stack, then load the archive once:

```bash
docker compose up --build -d
docker compose --profile import run --rm importer
```

The importer is deterministic and safe to run again after updating the archive. It is deliberately separate from `docker compose up`, so starting the application never silently downloads or changes data.

Open these local services:

* [CurlChat](http://localhost:5173)
* [FastAPI interactive API docs](http://localhost:8000/docs)
* [Phoenix tracing UI](http://localhost:6006) (tracing is disabled by default)

Stop the stack with `docker compose down`. PostgreSQL and Phoenix data remain in named Docker volumes. To intentionally start again with empty local data, run `docker compose down -v`, then repeat the import command.

### Development mode

The Docker stack uses Nginx to serve a production Vite build. For frontend iteration, run only the supporting services with `docker compose up -d postgres phoenix`, start the backend using the commands in the backend README, then run `pnpm install` and `pnpm dev` from `frontend`. Vite's development server serves the frontend on its own and proxies `/api` to FastAPI; it is not part of the Docker stack.

## Project structure

* `backend` — FastAPI application, agent orchestration, deterministic services, data models, and tests.
* `frontend` — React, TypeScript, and Vite chat interface.
* `docs` — architecture and implementation source of truth.
* `assets` — shared brand assets used by the README and frontend.

See the project overview in `docs/00-project-overview.md`.
