# AutoBets

Personal Betfair Exchange trading application (football and tennis first). Work in progress.

- `backend/` Python engine: price ladder, position and hedge maths, exchange interface, simulated exchange,
  write-ahead order journal, guardrails. Run the tests with `cd backend && python -m pytest`.
- Secrets never go in this repository (see `.gitignore`).

## Manual Trading screen (practice mode)

Backend: `backend/autobets/api/` (FastAPI). Frontend: `frontend/` (React + TypeScript + Vite); the built UI is committed in
`frontend/dist` so the server needs no Node. Rebuild with `cd frontend && npm ci && npm run build` before committing UI changes.

Run locally with fake prices (no Betfair needed):

    cd backend && AUTOBETS_MODE=demo python -m uvicorn --factory autobets.api.app:create_app --port 8000
    # open http://localhost:8000

Modes: `demo` (synthetic prices), `practice` (real delayed Betfair prices, simulated orders: nothing is ever sent to Betfair).
`practice` requires `AUTOBETS_TOKEN`. Live trading is not built yet.
Server install: see `deploy/autobets-api.service`.

## Deploying
Pushes to `main` that pass the tests are deployed to the practice server automatically (`.github/workflows/ci.yml`, job `deploy`).
The server pulls the new code and restarts the API unless stops or open orders are active, in which case it restarts on the next deploy once clear.
Log: `/opt/autobets/data/deploy.log`. One-time setup: `deploy/setup_autodeploy.sh`. Live mode is never restarted automatically.
