# Gridiron — Build Progress

**Status: all 10 milestones complete.** Built end-to-end autonomously against
real NFL data, with a real local Postgres and a real running frontend+backend
used for verification throughout (see notes below). The one substantive gap
is that the Docker Compose stack itself was never run through an actual
Docker daemon (none was available in the build sandbox) — everything it runs
was verified working outside a container instead. If you're picking this up
with Docker available, `docker compose up --build` is the one thing left to
actually confirm; nothing else should need further work.

Single source of truth for what's done and what's left. Any session (human or
agent) picking this project up should start here, then check `docs/build-spec.md`
for the original requirements.

Status legend: `[ ]` not started, `[~]` in progress, `[x]` done.

## Post-launch addition: keeping data current automatically

After the initial build, added a `scheduler` service (`backend/ml/scheduler.py`)
plus `backend/ml/season_config.py`. Two things this fixes:

1. **Staleness**: originally `/ingest` and `/predict` were purely manual, per
   spec's "out of scope: automation" — but that meant scores/predictions would
   never update on their own. The scheduler runs ingest+predict once a day
   (retrying every 5 min on failure instead of waiting a full day — mainly to
   ride out the race against the `api` container's own first-boot bootstrap).
   Training/backtesting are still manual on purpose — retraining on a schedule
   was never asked for and predictions don't need it (see point 2).
2. **A latent year-rollover bug**: `ingest.py`'s CLI defaults and
   `bootstrap.py` had hardcoded season ranges (`2018-2025`/`2018-2026`) that
   would have silently gone stale every year. Replaced with
   `season_config.py` helpers computed from the current date, including a
   Jan/Feb boundary case (games played in Jan/Feb belong to the *previous*
   NFL season, not the calendar year) — covered by 6 new tests in
   `test_season_config.py`. 25 backend tests passing total.

## Post-launch addition: in-season results now actually move predictions

User feedback after the scheduler was already in place: "what happens during
the season should actually influence the predictions." Fair — before this,
every prediction for a given matchup was frozen the moment the season's
model was trained, since features were pure prior-season stats. Fixed
properly rather than as a hack:

- New `weekly_team_stats` table (not in the original spec's schema — an
  intentional extension): one row per team/season/week holding that team's
  stats accumulated from games strictly *before* that week, computed in
  `ml/ingest.py::compute_weekly_rolling_stats`. Week 1 of every season is
  `games_played=0` with null stats by construction.
- `ml/features.py::build_feature_frame` now blends each team's prior-season
  stat with its current-season-to-date stat via a shrinkage formula
  (`PRIOR_SEASON_SHRINKAGE_GAMES = 6` — the entire prior season counts as 6
  current-season-equivalent games of evidence, so the blend crosses 50/50
  around a team's 7th game). At `games_played=0` this is mathematically
  identical to the old prior-season-only behavior, so it's a strict
  generalization, not a behavior change for week 1 or for any season with
  incomplete current-season data (e.g. right now — the 2026 season hasn't
  started, so 2026 week-1 predictions are unaffected).
- `turnover_margin` changed from a season *total* to a per-game *rate* in
  both `season_stats` and `weekly_team_stats` — required for the blend to be
  mathematically meaningful (can't shrinkage-blend a full-season sum against
  a 3-game partial sum on the same footing). Existing trained models were
  retrained after this change; nothing reads the old scale anymore.
  Frontend turnover margin displays were updated to match (2 decimal places,
  labeled "/ game").
- `GET /predictions/{game_id}` now also returns `home_current_stats` /
  `away_current_stats` (the raw in-season-to-date numbers), and the frontend
  shows a "this season so far" card + games-played count on the game detail
  page whenever either team has played at least one game.
- Ingest now fetches play-by-play **once** and reuses it for both
  `season_stats` and `weekly_team_stats` (was fetching it twice — cut a real
  ~80s of redundant network+compute off every ingest run).
- **Real impact, verified**: retrained + re-backtested against real data.
  Walk-forward accuracy (logreg) went from 58.1/58.1/55.9% (2023/24/25,
  prior-season-only) to 61.8/68.0/61.0% with blending — a meaningfully
  larger edge over the baseline (55.5/53.3/53.7%) than before. This is a
  real result, not tuning to the test set: the shrinkage constant was fixed
  by reasoning about games-to-convergence, not by trying values against the
  backtest.
- 32 → current backend test count includes new coverage for
  `blend_team_stats` (zero-games edge case, the shrinkage-games-exactly-even
  split, convergence toward current-season as games grow, missing-prior
  handling) and `build_feature_frame` blending end-to-end (including that an
  explicitly-empty `weekly_team_stats` frame behaves identically to omitting
  it, and that a weekly-stats row for the wrong week is correctly ignored).
  Frontend: 2 new tests for the in-season form card (absent vs. present).
- Ingest is slower now (~70-80s vs ~25-30s before) because of the added
  week-by-week aggregation — acceptable for a once-a-day background job, but
  worth knowing if it seems "stuck" during the Docker bootstrap step.

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
- [x] **9. README** — setup instructions, architecture, results table,
      screenshots (verified they actually render on GitHub via
      raw.githubusercontent.com, not just locally), API reference, project
      structure, MIT license added.
- [x] **10. Final verification + polish** — backend (19) and frontend (15)
      test suites re-run clean after all changes, `npm run build` clean, no
      stray files (`__pycache__`, `.pkl`, `.env`, `node_modules`) committed,
      GitHub repo description/topics set, all screenshot links confirmed
      live on GitHub, this file marked complete.

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
