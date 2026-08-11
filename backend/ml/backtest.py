"""Walk-forward backtest: for each test season, train only on strictly
earlier seasons, then predict the test season using each team's stats from
the season immediately before it. Compares against a home-team-always-wins
baseline. Writes one row per test season to backtest_results.

Usage:
    python -m ml.backtest --seasons 2023 2024 2025
    python -m ml.backtest --seasons 2023 2024 2025 --model-type xgboost
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss

from app.config import get_settings
from app.db import SessionLocal, engine
from app.models import BacktestResult
from ml.features import FEATURE_COLUMNS, LABEL_COLUMN, build_feature_frame
from ml.train import build_model

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backtest")


def _load_all_features() -> pd.DataFrame:
    games = pd.read_sql("SELECT * FROM games", engine)
    stats = pd.read_sql("SELECT * FROM season_stats", engine)
    return build_feature_frame(games, stats)


def run_backtest_for_season(
    all_features: pd.DataFrame, test_season: int, model_type: str
) -> dict | None:
    train_df = all_features[
        (all_features["season"] < test_season) & all_features[LABEL_COLUMN].notna()
    ]
    test_df = all_features[
        (all_features["season"] == test_season) & all_features[LABEL_COLUMN].notna()
    ]

    if train_df.empty or test_df.empty:
        logger.warning(
            "Skipping test_season=%d: train_rows=%d test_rows=%d",
            test_season,
            len(train_df),
            len(test_df),
        )
        return None

    X_train, y_train = train_df[FEATURE_COLUMNS], train_df[LABEL_COLUMN].astype(int)
    X_test, y_test = test_df[FEATURE_COLUMNS], test_df[LABEL_COLUMN].astype(int)

    model = build_model(model_type)
    model.fit(X_train, y_train)
    probs = model.predict_proba(X_test)[:, 1]
    preds = (probs >= 0.5).astype(int)

    accuracy = accuracy_score(y_test, preds)
    ll = log_loss(y_test, probs, labels=[0, 1])
    brier = brier_score_loss(y_test, probs)
    baseline_accuracy = accuracy_score(y_test, [1] * len(y_test))

    return {
        "test_season": test_season,
        "accuracy": float(accuracy),
        "log_loss": float(ll),
        "brier_score": float(brier),
        "baseline_accuracy": float(baseline_accuracy),
        "n_games": int(len(test_df)),
        "_model": model,
        "_train_rows": int(len(train_df)),
    }


def run_backtest(seasons: list[int], model_type: str, model_dir: str) -> list[dict]:
    all_features = _load_all_features()
    results = []
    for season in sorted(seasons):
        result = run_backtest_for_season(all_features, season, model_type)
        if result is None:
            continue
        model = result.pop("_model")
        train_rows = result.pop("_train_rows")
        version = f"{model_type}_bt_{season}"

        out_dir = Path(model_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, out_dir / f"model_{version}.pkl")

        logger.info(
            "season=%d train_rows=%d n_games=%d accuracy=%.3f baseline=%.3f log_loss=%.3f brier=%.3f",
            season,
            train_rows,
            result["n_games"],
            result["accuracy"],
            result["baseline_accuracy"],
            result["log_loss"],
            result["brier_score"],
        )
        results.append({**result, "model_version": version})

    write_results(results)
    return results


def write_results(results: list[dict]) -> None:
    if not results:
        return
    with SessionLocal() as db:
        for r in results:
            db.query(BacktestResult).filter_by(
                model_version=r["model_version"], test_season=r["test_season"]
            ).delete()
            db.add(
                BacktestResult(
                    model_version=r["model_version"],
                    test_season=r["test_season"],
                    accuracy=r["accuracy"],
                    log_loss=r["log_loss"],
                    brier_score=r["brier_score"],
                    baseline_accuracy=r["baseline_accuracy"],
                    n_games=r["n_games"],
                )
            )
        db.commit()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Walk-forward backtest of the gridiron model")
    parser.add_argument("--seasons", type=int, nargs="+", required=True)
    parser.add_argument("--model-type", choices=("logreg", "xgboost"), default="logreg")
    parser.add_argument("--model-dir", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    settings = get_settings()
    model_dir = args.model_dir or settings.model_dir
    run_backtest(seasons=args.seasons, model_type=args.model_type, model_dir=model_dir)


if __name__ == "__main__":
    main(sys.argv[1:])
