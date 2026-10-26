# Matchday Explainer

Football match catch-ups, plain-language stat explanations, and referee-law
explanations grounded in retrieved IFAB passages.

- **Backend:** Flask, Redis live state, saved JSONL matches, OpenAI, PostgreSQL/pgvector.
- **Frontend:** React + TypeScript + Vite. Design reference: `presentations/03-product-screens.png`.

## Run locally

Configure `backend/.env` as described in [backend/README.md](backend/README.md),
then run in separate terminals:

```sh
cd backend
./venv/bin/python app.py
```

```sh
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to Flask on port 8080.
Saved matches in `backend/data/synth` appear automatically. Live Redis state
takes priority while a match is replayed. AI and law retrieval require the
configured services; summary and stat fallbacks are clearly labelled.

## Checks

```sh
cd backend
./venv/bin/python -m unittest discover -s tests -v
```

```sh
cd frontend
npm run build
npm run lint
```
