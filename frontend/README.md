# CurlChat frontend setup plan

This repository does not yet include a generated Vite app. That is intentional for the first scaffold.

Recommended setup once backend foundations are in place:

1. create a React + TypeScript app with Vite
2. add routing only if conversation views require it
3. add a chat-focused feature layout rather than generic pages
4. add Plotly for chart rendering after response block contracts stabilize

Suggested commands:

- `pnpm create vite frontend-app --template react-ts`
- move generated contents into this `frontend/` directory
- `pnpm add plotly.js react-plotly.js`

Recommended source layout:

```text
src/
  app/
  components/
  features/
    chat/
    conversations/
    visualizations/
  lib/
  types/
```

Suggested first UI milestone:

- render a static conversation screen
- call the backend health endpoint
- add a non-streaming chat request
- introduce streaming only after the backend response contract is stable
