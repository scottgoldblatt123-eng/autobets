# AutoBets

Personal Betfair Exchange trading application (football and tennis first). Work in progress.

- `backend/` Python engine: price ladder, position and hedge maths, exchange interface, simulated exchange,
  write-ahead order journal, guardrails. Run the tests with `cd backend && python -m pytest`.
- Secrets never go in this repository (see `.gitignore`).
