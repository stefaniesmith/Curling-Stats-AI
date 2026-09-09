# CurlChat frontend

React, TypeScript, and Vite provide the chat-first interface for CurlChat's synchronous API. It renders Markdown, tables, summaries, and Plotly chart artifacts returned by the backend.

## Run locally

Start the FastAPI backend on port 8000, then run:

```bash
pnpm install
pnpm dev
```

Vite proxies `/api` to `http://localhost:8000`. Set `VITE_API_TARGET` to use another backend during development. Run `pnpm build` for a production build.

## Quality checks

Run `pnpm lint` for TypeScript and React linting, `pnpm format:check` to verify
Prettier formatting, or `pnpm check` to run linting, formatting, tests, and a
production build together. Use `pnpm format` to apply the configured formatting.

See [the frontend architecture document](../docs/08-frontend.md) for the UI design and boundaries.
