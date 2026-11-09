# AutoBets: technical document

Personal-use Betfair Exchange trading app (tennis, football). Practice mode only today: real delayed Betfair prices, simulated orders.

## Architecture
- **Backend** Python 3.13, FastAPI (`backend/autobets`). One `Engine` (RLock-guarded, state saved to `state.json` after every call) behind `api/app.py`.
- **Frontend** React 18 + TypeScript + Vite (`frontend/src`); the built `frontend/dist` is committed and served by the backend. Screens switch by URL hash (`#home`, `#settings`, ...).
- **Deploy** GitHub Actions on push to main: tests, then deploy to a DigitalOcean droplet (Caddy HTTPS, systemd service `autobets-api`). Data in `/opt/autobets/data`, secrets in `/opt/autobets/secrets`.
- **Modes** `AUTOBETS_MODE=demo|practice`. `live` is refused at start-up on purpose.

## Exchange layer
`exchange/base.py` is the one interface. `SimulatedExchange` (matching on recorded books), `PracticeExchange` (refreshes books from the real feed, orders stay simulated) and `BetfairAdapter` (read prices; placeOrders / cancelOrders / replaceOrders / listCurrentOrders built but off unless `enable_trading("SEND-REAL-ORDERS")`; mock-tested only; not wired into the engine).

## Live mode (built, switched off)
`AUTOBETS_MODE=live` additionally needs `AUTOBETS_LIVE_CONFIRM=SEND-REAL-ORDERS`; it uses separate state and journal files (`live_state.json`, `live_journal.db`) so practice history never mixes with real. `exchange/live.py` (`LiveExchange`) mirrors Betfair's orders locally (listCurrentOrders at most every 1.5 s), derives fills from matched-size changes, and starts **disarmed**: no new order until Settings > Live trading is armed with the phrase `SEND-REAL-ORDERS` (resets on every restart). Cancels always work. At start-up `reconcile()` compares saved orders with Betfair and alerts on differences. After each settlement the computed result is compared with `listClearedOrders`. `deploy.sh` never restarts a live server automatically. Not yet built: the streaming API (prices are polled) and in-play bet-delay handling beyond recording `betDelay`.

## Backups and monitoring
`backup.py` runs a daily online backup of every SQLite database and JSON state file into `data/backups/YYYY-MM-DD/` (7 days plus 4 Sundays), with a disk-space check. Health shows backup age and disk. `.github/workflows/uptime.yml` pings the server every 15 minutes and fails (so GitHub emails) when it does not answer. On-box backups do not protect against losing the server: enable DigitalOcean droplet backups for that.

## Order path and safety
`OrderService` journals before sending (SQLite journal, idempotent on `client_ref`), then calls the guardrails, then the exchange.
Each order has a `source`: `manual`, `script:<name>`, `script:<name>:exit`, `ai`.
- Manual: no guardrails.
- Automation: kill switch (Stop all automation), daily and weekly loss limits (0 = not set), open liability limit, stake caps.
- `:exit` sources bypass loss/exposure limits (so a script can always close) but not the kill switch.
Guard inputs: `realised_today/week` (settled plus mark-to-market of open positions) and `open_exposure` (worst case; automation-only unless "include manual"). Manual P&L counts toward limits but never blocks manual bets.

## Money
`ledger.py` books each settled market (UK-time day and week) with per-strategy attribution (`parts`) and `staked` for ROI. `settle_check` runs about every 15 s.

## Scripts and Plan
`scripts.py`: JSON rules, validator, evaluator, versioned store. Entry/exit/safety rules; conditions price, in_play, set_number, goals_total, score_is, minute, rule_matched, position_loss, clock, ticks_from_entry, ticks_from_peak (trailing stop), minutes_to_start, spread_ticks, market_matched, price_move; entry rules may `repeat` up to 100 runs; actions back/lay/green/close/stop. `plan.py` binds a script to a market and runner with stake. The runner `run_scripts` runs every 2 s in the background loop using the live match context (`match_context.for_market`).

## Recommendations
`recs.py` scans pre-match markets within 8 h: model price vs market, edge >= 4 points, spread <= 6 ticks, price <= 8, max 8 pending, confidence never High. CLV is measured at go-in-play. Auto-apply and Full AI are locked until 300 evidenced recommendations with positive CLV.

## Alerts and health
`alerts.py` stores alerts with key-based de-duplication. `health.py` reports Betfair (via `_TrackedFeed`), tennis, football, price log and Claude. A monitor thread runs every 60 s (alerts) and scans recommendations every 2 min.

## Data and models
- SQLite: `football.db` (API-Football), `tennis_api.db` (api-tennis), `prices.db` (Betfair price log, plus recorded winners in `results`), `ai.db` (Claude usage).
- Tennis models v1, v2, Elo, v3 (best offline 63.1% vs market about 68-70%); football 1X2 Poisson/Dixon-Coles (49.7% vs 43.9% baseline). They are trading guidance (price movement), not winner-picking.
- Backtest (`backtest.py`): replays the price log on markets with a recorded winner; fills at the best recorded price with unlimited size, 5% commission, last 30% held out.

## API (all under /api, bearer token except demo)
settings (GET/PUT), automation/stop, pnl, scripts (CRUD, enable, clone, build), plan (+bets), recs (+apply, dismiss, scan), alerts (+read, resume), health, home, credentials (presence only), analyse/performance|models|ai, backtests, plus the market, ladder, order, green, dutch, copilot and status endpoints from earlier stages.

## Tests
`cd backend && python3 -m pytest tests -q` (209) and `cd frontend && npx vitest run`. `docs/uat_cases.py` generates the UAT script.

## Known limits
Queue position and own-order market impact are not simulated (practice flatters fast trading); football red cards are not modelled; scripts are edited as JSON (no visual builder); email/push alerts not set up; real orders unwired; backtests need recorded results to accumulate.

### Market listing by day
`GET /api/markets?sport=&date=YYYY-MM-DD` lists a UK calendar day. `Engine._markets_on` splits the day into 3-hour `marketStartTime` windows (Betfair caps catalogue results at ~100), merges and sorts them; cached 30 s per sport+day. No `date` keeps the "next to start" list. Demo mode returns markets for today only.

### Trade setups (recommendations v2)
`setups.py` holds the generators: `tennis()` (market vs model win probability picks the lean; entry needs `set_games_diff` and a >=12% price reaction), `football()` (pre-match `pre_model.over_2.5` from `context._football` vs the normalised Over/Under 2.5 book, found via `engine.event_markets`). `Recs.scan` calls them; `upsert_setup` keeps one pending setup per market+template. `Engine._accept_setup` creates the script (origin ai, enabled; name de-duplicated with "#2") and a Plan row; it places no order. New script conditions: `set_games_diff`, `sets_diff` (need `view.player_idx`, matched from the runner name). `result` is filled from the ledger when the market settles. The old winner-edge `Recs.candidate` is no longer called by the scan.
Not yet done: replaying setup scripts over the recorded price log (needs in-play scores recorded alongside prices).

### Script proposals
`ai/scriptideas.py` builds a prompt from the library (`Engine.script_library`) and accepted-setup results (`setup_results`), asks Claude for N ideas in an IDEA/WHY/RISK/```script format, and keeps those that pass `scripts.validate`. `Recs.add_proposal` stores them as kind `script` (deduped by title); `Engine._accept_proposal` saves the script disabled. `POST /api/recs/propose-scripts`; the monitor loop runs it at most once a day when a key is configured and no proposal is under 20 h old. Tennis setups: `tennis_swing_*` when the model leans (gap >= 1.5 pts), `tennis_fade_lay` otherwise. Pending cap is per sport (12).

### Starter library
`starters.py` holds `STARTERS` (id, sport, title, summary, attach, caveats, script) and `UNSUPPORTED` (title, reason). `GET /api/starters` returns them with plain-English rule text and an `added` flag (matched by script name); `POST /api/starters/{id}/add` creates the script disabled (origin "you", note "added from the starter library"; 409 if already there). New tennis conditions used by starters: `breaks_diff` (derived from games and who serves; false when the server is unknown or 12+ games), `serving`, `game_points_diff`, `game_score_is`, `break_point`, `set_games_total`, `prev_set_games_diff`; football `half_time`; green/close accept `percent`. `tests/test_starters.py` validates every starter.

### Setup scripts are shared
`_accept_setup` looks up the library script by its (match-free) name and reuses it, creating it only if missing. Price conditions can be relative (`{"type":"price","op":">=","rel":1.12,"ref":"back"}`): the threshold is `rel x row.ref_price`, where `ref_price` is stored on the Plan row at accept time and passed in `_script_view`. No `ref_price` means the condition is false.

### Analyse ranges
`GET /api/analyse/performance` accepts `days` (legacy: last N days v the N before) or `start`, `end` (UK dates, end inclusive) with optional `cstart`, `cend`. `analyse.performance_between` returns the same shape plus `compare`, per-strategy `prev_trades`/`prev_pnl`, and the comparison curve shifted onto the main period. Frontend: `DateRange.tsx` (preset maths in `presetRange`/`cmpRange`, unit-tested).

### Diagnostics and stale entries
`GET /api/plan/{id}/why` (`Engine.plan_why`) evaluates each rule's conditions with `scripts.check` against the live view and returns them with `describe_cond` text plus readings. `Engine._stale_entry` (45s, `STALE_ENTRY_S`) cancels a script entry order that has no fills and re-arms the same cycle; previously an unmatched entry left the row Running with no exit able to fire (exits need a matched entry) and no repeat.

### Scan funnel
`Recs.scan` records `last_scan` (per sport: markets, soon, priced, with_context, with_model, setups, errors[]), returned as `scan` by `GET /api/recs`. Errors from price requests, market listing and setup generation are recorded there instead of being swallowed. `setups.tennis` falls back to market-implied odds when there is no rating model; `setups.football` falls back to the market's Over probability (so only the scalp, which needs no edge, can qualify).
