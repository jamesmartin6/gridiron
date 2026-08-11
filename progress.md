# Gridiron — Build Progress

Single source of truth for what's done and what's left. Any session (human or
agent) picking this project up should start here, then check `docs/build-spec.md`
for the original requirements.

Status legend: `[ ]` not started, `[~]` in progress, `[x]` done.

## Milestones

- [x] **1. Data ingestion** — `backend/ml/ingest.py` pulls schedules + play-by-play
      via `nfl_data_py` (2018–2026), computes season-level team stats, upserts into
      Postgres (`teams`, `season_stats`, `games`). Verified against a real local
      Postgres 16 instance — realistic output (e.g. KC 2024 win_pct = 0.882 = 15-2,
      matches real-world record).
      - Design decision: used `import_pbp_data` instead of `import_weekly_data` for
        team stats, because weekly data is player-offense-only and has no defensive
        signal, so `epa_defense` can't be derived from it. PBP has `posteam`/`defteam`
        on every row, giving correct offense *and* defense aggregates. Points and
        win_pct still come from `import_schedules`, per spec.
- [x] **2. Feature engineering + training** — `backend/ml/features.py` builds
      prior-season diff features (season N game uses N-1 stats for both teams,
      drops games missing prior stats). `backend/ml/train.py` trains logreg
      (default) or xgboost, serializes to `ml/artifacts/model_<version>.pkl` +
      a metadata JSON.
- [x] **3. Backtest** — `backend/ml/backtest.py` walk-forward validates: for each
      test season, trains only on strictly earlier seasons, predicts the test
      season using prior-season stats, computes accuracy/log_loss/brier vs a
      home-team-always baseline. Verified for 2023/2024/2025 (logreg beats
      baseline in all three seasons post-bugfix — see below; xgboost slightly
      underperforms logreg on this small a feature set, which is a real and
      expected result on ~1000-1600 training rows, not a bug). Results written
      to `backtest_results`.
- [x] **4. FastAPI backend** — models/schemas/routers for teams, games,
      predictions, backtest; `/ingest` and `/predict` admin endpoints. All
      endpoints manually verified against the real local Postgres instance.
- [x] **5. Backend tests** — 19 pytest tests: feature engineering (pure unit
      tests), full ML pipeline (train/backtest/predict against synthetic
      DB-seeded data, no network dependency), API endpoints via `TestClient`
      against a throwaway `gridiron_test` database. All passing.
      **Caught a real bug**: the original `build_feature_frame` join was
      off by one season in the wrong direction — it joined each game against
      stats from *two* seasons prior instead of one (a season+1/season-1
      double-shift in the merge keys), silently "working" on real data only
      because it happened to produce a non-empty, plausible-looking result
      starting from 2020 instead of 2019. Fixed in `ml/features.py`; all real
      models/backtests/predictions were regenerated after the fix. Corrected
      backtest (logreg, 2023/2024/2025): accuracy 0.581/0.581/0.559 vs
      baseline 0.555/0.533/0.537 — beats the home-favorite baseline in all
      three seasons.
- [x] **6. React frontend** — Vite + React 19 + TypeScript. Three pages: This
      Week (sortable table, season/week selectors), Game Detail (win prob +
      feature-diff bars + raw season stats for both teams), Model Accuracy
      (recharts bar chart of accuracy vs. baseline per season + full metrics
      table). Verified visually with a headless-Chromium (Playwright) script
      driving the real running app against real data — screenshots looked
      right, zero console errors. One false alarm worth recording: a
      Playwright `fullPage: true` screenshot taken immediately after
      navigation raced the chart's own resize-triggered re-render and
      captured a blank frame; the chart itself was always correct (confirmed
      via direct SVG inspection and a manual resize test) — not an app bug,
      just a screenshot-tool timing artifact.
- [x] **7. Frontend tests + build** — 15 vitest + Testing Library tests
      (components, all three pages with mocked API client), `npm run build`
      and `tsc -b` both clean.
- [x] **8. Docker Compose** — db (postgres:16-alpine, healthchecked) + api +
      frontend (nginx serving the Vite build). `backend/ml/bootstrap.py` runs
      automatically on API container start: if `season_stats` is empty it
      runs ingest → train → backtest → predict once (idempotent — skips
      instantly once data exists), so `docker compose up --build` alone is a
      genuine one-command path to a fully working app, not just an empty
      shell needing manual setup. Verified the entire bootstrap flow
      (ingest/train/backtest/predict end-to-end from a truly empty database)
      against the real local Postgres. **Not container-tested** — no Docker
      available in this sandbox (see Environment notes below); Dockerfiles
      and compose YAML are syntax-validated and path-checked but the actual
      `docker compose up --build` has not been run. Do that first if picking
      this up with Docker available, and fix anything that breaks.
- [ ] **9. README** — setup instructions, architecture, how to re-run
      ingest/train/backtest, screenshots.
- [ ] **10. Final verification + polish** — full pipeline run end-to-end, clean
      history, progress.md marked complete.

## Environment notes for whoever resumes this

- **No Docker available in the dev sandbox.** Dockerfiles/compose are written
  carefully but only syntax/logic-reviewed, not container-tested. If you have
  Docker, `docker compose up --build` is the real test — do that first and fix
  anything that breaks.
- **Python**: sandbox's default `python3` is 3.14 (MSYS2, no usable pip wheels
  for the ML stack). Used a separate Python 3.12 install instead:
  `C:\Users\James\AppData\Local\Programs\Python312-taskflow\python.exe` to
  create `backend/.venv`. That path belongs to an unrelated project on this
  machine ("taskflow") — only used as a Python interpreter source, nothing
  from it is imported or depended upon.
- **nfl_data_py pin conflict**: `nfl_data_py==0.3.3` declares `numpy<2` and
  `pandas<2` in its own metadata, but pandas 1.5.3 has no Python 3.12 wheel
  and fails to build from source. It runs fine against modern pandas/numpy in
  practice (verified against real 2023/2024 data), so it's installed with
  `pip install nfl_data_py==0.3.3 --no-deps` after pandas 2.2.3 / numpy 1.26.4
  are already in place. See `backend/requirements.txt` install order — don't
  "fix" this by just running `pip install -r requirements.txt` blindly if
  nfl_data_py isn't already satisfied; check it imports and pulls data after
  any dependency changes.
- **Local Postgres for dev/test**: no Docker means no easy Postgres. Used the
  EnterpriseDB portable Windows zip (no installer) to run a real Postgres 16
  on port 5433, data dir under the session's OS temp scratchpad (kept out of
  the OneDrive-synced project folder on purpose — a live Postgres data
  directory being continuously synced by OneDrive is a corruption risk).
  `backend/.env` (gitignored) points at `localhost:5433`; `.env.example`
  documents the docker-compose values (port 5432) for real use. If picking
  this up fresh without that temp Postgres still running, either start a new
  one the same way or just use `docker compose up db`.
- Real ingested data covers seasons 2018–2026: `season_stats` for 2018–2025
  (needs completed games), `games` through 2026 (schedule already published,
  scores pending — that's what lets `/predict` produce upcoming-week
  predictions right now using 2025 stats).

## Decisions made autonomously (per user instruction not to be asked)

- DB schema matches `docs/build-spec.md` section 4 exactly, including
  `predictions` (no stored feature columns). Game-detail "why" breakdown is
  computed on the fly from `season_stats` at request time instead of adding
  columns — keeps the schema faithful to spec while still meeting the
  frontend requirement to show feature diffs.
- GitHub repo: public, at `github.com/jamesmartin6/gridiron`.
