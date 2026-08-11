"""Loads a trained model and produces home_win_prob for games.

Usage:
    python -m ml.predict --version logreg_v1 --season 2026 --week 1
    python -m ml.predict --version logreg_v1 --season 2026
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import joblib
import pandas as pd

from app.config import get_settings
from app.db import SessionLocal, engine
from app.models import Prediction
from ml.features import FEATURE_COLUMNS, build_feature_frame

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("predict")


def load_model(version: str, model_dir: str):
    path = Path(model_dir) / f"model_{version}.pkl"
    if not path.exists():
        raise FileNotFoundError(f"No model found at {path}. Run ml.train first.")
    return joblib.load(path)


def predict_games(
    model,
    games: pd.DataFrame,
    season_stats: pd.DataFrame,
    weekly_team_stats: pd.DataFrame | None = None,
) -> pd.DataFrame:
    feat = build_feature_frame(games, season_stats, weekly_team_stats)
    if feat.empty:
        return feat.assign(home_win_prob=pd.Series(dtype=float))
    probs = model.predict_proba(feat[FEATURE_COLUMNS])[:, 1]
    feat = feat.copy()
    feat["home_win_prob"] = probs
    return feat


def run_predict(
    version: str, model_dir: str, season: int, week: int | None = None
) -> int:
    model = load_model(version, model_dir)

    games_query = "SELECT * FROM games WHERE season = %(season)s"
    params: dict = {"season": season}
    if week is not None:
        games_query += " AND week = %(week)s"
        params["week"] = week
    games = pd.read_sql(games_query, engine, params=params)
    stats = pd.read_sql("SELECT * FROM season_stats", engine)
    weekly_stats = pd.read_sql("SELECT * FROM weekly_team_stats", engine)

    result = predict_games(model, games, stats, weekly_stats)
    if result.empty:
        logger.warning("No games with available prior-season stats for season=%s week=%s", season, week)
        return 0

    with SessionLocal() as db:
        for _, row in result.iterrows():
            db.query(Prediction).filter_by(
                game_id=row["game_id"], model_version=version
            ).delete()
            db.add(
                Prediction(
                    game_id=row["game_id"],
                    model_version=version,
                    home_win_prob=float(row["home_win_prob"]),
                )
            )
        db.commit()

    logger.info("Wrote %d predictions (model=%s season=%s week=%s)", len(result), version, season, week)
    return len(result)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate predictions for games")
    parser.add_argument("--version", default=None, help="Defaults to configured DEFAULT_MODEL_VERSION")
    parser.add_argument("--model-dir", default=None)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    settings = get_settings()
    version = args.version or settings.default_model_version
    model_dir = args.model_dir or settings.model_dir
    run_predict(version=version, model_dir=model_dir, season=args.season, week=args.week)


if __name__ == "__main__":
    main(sys.argv[1:])
