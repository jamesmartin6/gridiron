# 🏈 Gridiron

**NFL game outcome predictions from prior-season team stats — with a walk-forward backtest to prove the model isn't fooling itself.**

Gridiron pulls real NFL play-by-play and schedule data, builds a feature set from each team's *prior-season* performance, trains a win-probability model, and validates it the way it'll actually be used: predicting a season using only the season before it, repeated across multiple years. Full stack, containerized, tested end-to-end against real data.

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white">
  <img alt="React" src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=white">
  <img alt="TypeScript" src="https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white">
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white">
  <img alt="Docker" src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-blue">
</p>

<p align="center">
  <img src="docs/screenshots/this-week.png" width="90%" alt="This Week — sortable table of upcoming games with model win probabilities">
</p>

## Why this exists

Most "NFL predictor" side projects report a single accuracy number and call it done. The interesting question is different: **does a model trained the way you'd actually use it — last season predicting this one — actually beat just picking the home team?** Gridiron is built around answering that honestly:

- Every feature is computed from a team's **prior season only**. A season-N game never sees season-N data, even indirectly.
- The backtest is **walk-forward**: for each test season, the model is trained *only* on strictly earlier seasons, then evaluated on the test season using the season immediately before it — exactly the setup a live prediction would use.
- It's checked against the obvious baseline (always pick the home team) every time, not just once.

## Results

Walk-forward backtest, logistic regression, three most recent completed seasons:

| Test season | Accuracy | Home-favorite baseline | Log loss | Brier score |
|---|---|---|---|---|
| 2023 | **58.1%** | 55.5% | 0.672 | 0.240 |
| 2024 | **58.1%** | 53.3% | 0.669 | 0.238 |
| 2025 | **55.9%** | 53.7% | 0.694 | 0.250 |

Beats the baseline in all three seasons using only five prior-season team stats. An XGBoost variant is also included for comparison — it does *not* consistently beat logistic regression here, which is a real and expected result given how few features and rows this problem has (~1,000–1,600 training rows, 6 features), not a bug. See [`docs/build-spec.md`](docs/build-spec.md) and [`progress.md`](progress.md) for the full methodology notes and a couple of real bugs the test suite caught along the way.

<p align="center">
  <img src="docs/screenshots/model-accuracy.png" width="90%" alt="Model Accuracy page — backtest chart and metrics table">
</p>

## How a prediction is made

For a game between a home and away team in season *N*, the feature vector is entirely made of season-*(N-1)* stat diffs:

`epa_offense_diff` · `epa_defense_diff` · `turnover_margin_diff` · `win_pct_diff` · `yards_per_play_diff` · `home_flag`

Team-level offensive *and* defensive EPA come from play-by-play data rather than `nfl_data_py`'s weekly summaries — weekly data is player-offense-only with no defensive signal, so `epa_defense` can't be derived from it. Play-by-play carries `posteam`/`defteam` on every row, which gives both sides correctly. Games where a team has no prior-season stats (e.g. the edge of the data window) are dropped from training and evaluation, per spec.

The game detail page shows exactly why the model favors a team — the same diffs it was trained on, visualized:

<p align="center">
  <img src="docs/screenshots/game-detail.png" width="90%" alt="Game detail page — win probability and feature breakdown">
</p>

## Stack

| Layer | Tech |
|---|---|
| Data source | [`nfl_data_py`](https://github.com/nflverse/nfl_data_py) (schedules + play-by-play, sourced from nflverse) |
| ML | pandas, scikit-learn (logistic regression), XGBoost (optional) |
| API | FastAPI + SQLAlchemy 2.0 |
| Database | PostgreSQL 16 |
| Frontend | React 19, TypeScript, Vite, react-router, recharts |
| Infra | Docker Compose (db + api + frontend) |

## Quickstart (Docker)

```bash
git clone https://github.com/jamesmartin6/gridiron.git
cd gridiron
docker compose up --build
```

That's it. On first boot, the API container automatically pulls the last several seasons of real NFL data, trains the default model, runs the backtest, and predicts the current season's games — no manual steps required. It's idempotent, so restarting the stack later won't re-pull or re-train.

- Frontend: <http://localhost:5173>
- API docs (Swagger): <http://localhost:8000/docs>

To re-run any step manually (e.g. after a new season's games are played):

```bash
docker compose exec api python -m ml.ingest
docker compose exec api python -m ml.train --seasons 2020 2021 2022 2023 2024 2025
docker compose exec api python -m ml.backtest --seasons 2023 2024 2025
docker compose exec api python -m ml.predict --version logreg_v1 --season 2026
```

> **Note:** the Dockerfiles and compose config were built and syntax/path-validated in a sandbox without a Docker daemon available — the full pipeline they run (ingest → train → backtest → predict) was verified end-to-end against a real local Postgres instance instead. If `docker compose up --build` surfaces anything, it's most likely a container-specific wrinkle rather than a logic bug; see [`progress.md`](progress.md) for exactly what was and wasn't container-tested.

## Local development (without Docker)

<details>
<summary>Backend</summary>

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
pip install nfl_data_py==0.3.3 --no-deps   # see requirements.txt for why this is separate

cp .env.example .env   # point DATABASE_URL at your Postgres

python -m ml.ingest
python -m ml.train --seasons 2020 2021 2022 2023 2024 2025
python -m ml.backtest --seasons 2023 2024 2025
python -m ml.predict --version logreg_v1 --season 2026

uvicorn app.main:app --reload
pytest
```
</details>

<details>
<summary>Frontend</summary>

```bash
cd frontend
npm install
cp .env.example .env   # point VITE_API_BASE_URL at your API
npm run dev
npm test
npm run build
```
</details>

## API

| Endpoint | Description |
|---|---|
| `GET /teams` | All teams |
| `GET /teams/{team_id}/stats?season=` | A team's season stat line |
| `GET /games?season=&week=` | Games for a season/week, with predictions attached (defaults to the latest upcoming week) |
| `GET /predictions/{game_id}` | Prediction + full feature breakdown for one game |
| `GET /backtest` | All backtest results (accuracy/log-loss/Brier vs. baseline, per season) |
| `POST /predict?season=&week=` | Admin: runs the current model over a season/week and writes predictions |
| `POST /ingest` | Admin: refreshes teams/season_stats/games from `nfl_data_py` |

Full interactive docs at `/docs` once the API is running.

## Project structure

```
gridiron/
  backend/
    app/            # FastAPI app: models, schemas, routers, config
    ml/              # ingest, features, train, backtest, predict, bootstrap
    tests/            # pytest — unit, ML pipeline, API (against a real throwaway Postgres db)
    Dockerfile
  frontend/
    src/
      pages/          # ThisWeek, GameDetailPage, BacktestPage
      components/     # WinProbBar, DiffBar, Nav
      api/            # typed fetch client
    Dockerfile
  docs/
    build-spec.md     # original project spec
    screenshots/
  docker-compose.yml
  progress.md          # build log: what's done, decisions made, bugs found
```

## Testing

- **Backend**: 19 pytest tests — feature-engineering unit tests, full ML pipeline (train/backtest/predict) against deterministic synthetic data seeded into a real Postgres, and API endpoint tests via `TestClient` against a throwaway `_test` database. `cd backend && pytest`.
- **Frontend**: 15 Vitest + Testing Library tests covering all three pages and shared components. `cd frontend && npm test`.
- The whole app was also driven end-to-end in a real headless browser (screenshots above) to confirm it actually renders against live data with no console errors — not just that the test suites pass.

## Scope

Regular season only; no playoff modeling, no betting-line integration, no player-level injury data, no automated retraining (`/ingest` and `/predict` are manual/on-demand triggers — see [`docs/build-spec.md`](docs/build-spec.md) for the full original spec this was built against).

## License

[MIT](LICENSE)
