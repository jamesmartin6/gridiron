# Gridiron — NFL Game Outcome Predictor — Build Spec

## 1. Goal

Build a full-stack website that predicts NFL game outcomes using each team's
**prior-season** stats. Include a backtesting pipeline that trains on the last
few completed seasons and validates predictions against the most recently
completed season's actual results.

## 2. Tech Stack

- **Data pipeline / model**: Python, `nfl_data_py`, `pandas`, `scikit-learn` (or `xgboost`)
- **Backend API**: Python, FastAPI
- **Database**: PostgreSQL
- **Frontend**: React (Vite), TypeScript
- **Containerization**: Docker Compose (db + api + frontend)

## 3. Data Source

Use `nfl_data_py` to pull:
- `import_schedules(years)` — game results (home/away teams, scores, week, season)
- `import_weekly_data(years)` — weekly team/player stats, aggregate to season level

Pull at least the last **5 seasons** so there's enough history for backtesting
across multiple prior seasons.

## 4. Database Schema

```sql
CREATE TABLE teams (
    team_id     TEXT PRIMARY KEY,
    name        TEXT NOT NULL
);

CREATE TABLE season_stats (
    team_id         TEXT REFERENCES teams(team_id),
    season          INT NOT NULL,
    points_for      NUMERIC,
    points_against  NUMERIC,
    epa_offense     NUMERIC,
    epa_defense     NUMERIC,
    turnover_margin NUMERIC,
    yards_per_play  NUMERIC,
    win_pct         NUMERIC,
    PRIMARY KEY (team_id, season)
);

CREATE TABLE games (
    game_id     TEXT PRIMARY KEY,
    season      INT NOT NULL,
    week        INT NOT NULL,
    home_team   TEXT REFERENCES teams(team_id),
    away_team   TEXT REFERENCES teams(team_id),
    home_score  INT,
    away_score  INT,
    game_date   DATE
);

CREATE TABLE predictions (
    game_id         TEXT REFERENCES games(game_id),
    model_version   TEXT NOT NULL,
    home_win_prob   NUMERIC NOT NULL,
    predicted_at    TIMESTAMP DEFAULT now(),
    PRIMARY KEY (game_id, model_version)
);

CREATE TABLE backtest_results (
    id              SERIAL PRIMARY KEY,
    model_version   TEXT NOT NULL,
    test_season     INT NOT NULL,
    accuracy        NUMERIC,
    log_loss        NUMERIC,
    brier_score     NUMERIC,
    baseline_accuracy NUMERIC,   -- always-pick-home-team baseline
    n_games         INT,
    run_at          TIMESTAMP DEFAULT now()
);
```

## 5. Feature Engineering

For each game, build a feature vector from **each team's stats from the prior
season** (season N game uses season N-1 stats for both teams):

- `epa_offense_diff` = home.epa_offense − away.epa_offense
- `epa_defense_diff` = home.epa_defense − away.epa_defense
- `turnover_margin_diff`
- `win_pct_diff`
- `yards_per_play_diff`
- `home_flag` = 1 (always, since home team is fixed per row)

Label: `home_team_won` (1/0), derived from `home_score > away_score`.

Games where a team has no prior-season stats (e.g. first year of data window)
should be dropped from training/eval.

## 6. Model

- Logistic regression as the baseline model; `xgboost` classifier as a second
  option, selectable via config.
- Train script: `train.py`
  - Input: seasons to train on
  - Output: serialized model file (`model_<version>.pkl`) + feature list
- Predict script/service loads the model and outputs `home_win_prob` per game.

## 7. Backtesting Plan (walk-forward validation)

This is the core requirement — validate the model the way it'll actually be used.

1. Pull the last 5 seasons of data, e.g. seasons `2020–2024`.
2. For **test season = 2024**: train on season stats through 2023 (using
   2022 stats to predict 2023 games, 2023 stats to predict 2024 games —
   i.e. every training row uses the prior season's stats, matching the
   real prediction setup).
3. Predict every regular-season game in 2024 using each team's 2023 stats.
4. Compare predictions to actual 2024 results. Compute:
   - **Accuracy** (correct winner picked)
   - **Log loss**
   - **Brier score**
   - **Baseline accuracy**: accuracy of always picking the home team, for comparison
5. Repeat for test season = 2023 (train through 2022, predict 2023 using 2022 stats), and 2022, so you get backtest results across **at least 3 prior seasons**, not just one.
6. Write each season's results to `backtest_results`.
7. Expose backtest results via API + a simple chart on the frontend (accuracy
   per season vs. baseline).

Script: `backtest.py`, runnable standalone (`python backtest.py --seasons 2022 2023 2024`).

## 8. API Endpoints (FastAPI)

- `GET /teams/{team_id}/stats?season=` → season stat line for a team
- `GET /games?season=&week=` → games with predictions attached (join `games` + `predictions`)
- `GET /predictions/{game_id}` → prediction + feature breakdown for one game
- `GET /backtest` → all backtest_results rows (for the accuracy chart)
- `POST /predict` → admin/internal endpoint; runs the current model over
  upcoming games (or a given season/week) and writes to `predictions`
- `POST /ingest` → admin/internal endpoint; pulls fresh data via `nfl_data_py`
  and refreshes `teams`, `season_stats`, `games`

## 9. Frontend (React)

Pages:
- **Home / This Week** — table of current week's games with predicted home
  win probability, sortable
- **Game Detail** — feature breakdown for a single game (why the model picked
  what it picked — show the diffs)
- **Backtest / Model Accuracy** — chart of accuracy vs. baseline per test
  season, plus overall log loss / Brier score

Keep styling simple — a clean table-driven UI is fine, this isn't the focus.

## 10. Project Structure

```
nfl-predictor/
  backend/
    app/
      main.py
      models.py        # SQLAlchemy models matching schema above
      schemas.py        # Pydantic response models
      routers/
        teams.py
        games.py
        predictions.py
        backtest.py
      db.py
    ml/
      ingest.py          # pulls data via nfl_data_py, populates db
      features.py        # builds feature vectors
      train.py
      backtest.py
      predict.py
    Dockerfile
  frontend/
    src/
      pages/
      components/
      api/
    Dockerfile
  docker-compose.yml
  README.md
```

## 11. Milestones

1. Data ingestion script working end-to-end into Postgres
2. Feature engineering + training script producing a model
3. Backtest script producing accuracy/log-loss/Brier metrics vs. baseline for 3 seasons
4. FastAPI endpoints wired to db + model
5. React frontend consuming the API (weekly predictions + backtest chart)
6. Docker Compose bringing up the full stack with one command
7. README documenting setup, how to re-run ingestion/training/backtest

## 12. Out of Scope (for this version)

- Live/in-season model retraining automation (cron jobs) — manual trigger via `/ingest` and `/predict` is enough
- Player-level injury data or betting line integration
- Playoff-specific modeling (regular season only)
