"""Trains a home-win-probability model on prior-season stat diffs.

Usage:
    python -m ml.train --seasons 2020 2021 2022 2023 --model-type logreg
    python -m ml.train --seasons 2020 2021 2022 2023 --model-type xgboost --version xgb_v1
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.config import get_settings
from app.db import engine
from ml.features import FEATURE_COLUMNS, LABEL_COLUMN, build_feature_frame

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("train")

MODEL_TYPES = ("logreg", "xgboost")


def load_training_frame(seasons: list[int]) -> pd.DataFrame:
    games = pd.read_sql("SELECT * FROM games", engine)
    stats = pd.read_sql("SELECT * FROM season_stats", engine)
    feat = build_feature_frame(games, stats)
    feat = feat[feat["season"].isin(seasons)]
    feat = feat.dropna(subset=[LABEL_COLUMN])
    return feat


def build_model(model_type: str):
    if model_type == "logreg":
        return Pipeline(
            [
                ("scaler", StandardScaler()),
                ("clf", LogisticRegression(max_iter=1000)),
            ]
        )
    if model_type == "xgboost":
        from xgboost import XGBClassifier

        return XGBClassifier(
            n_estimators=200,
            max_depth=3,
            learning_rate=0.05,
            subsample=0.9,
            colsample_bytree=0.9,
            eval_metric="logloss",
        )
    raise ValueError(f"Unknown model_type: {model_type}. Choose from {MODEL_TYPES}")


def train(seasons: list[int], model_type: str, version: str, model_dir: str) -> dict:
    frame = load_training_frame(seasons)
    if frame.empty:
        raise RuntimeError(
            f"No labeled training rows found for seasons {seasons}. Run ingest first."
        )

    X = frame[FEATURE_COLUMNS]
    y = frame[LABEL_COLUMN].astype(int)

    logger.info("Training %s on %d rows from seasons %s", model_type, len(frame), seasons)
    model = build_model(model_type)
    model.fit(X, y)

    out_dir = Path(model_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    model_path = out_dir / f"model_{version}.pkl"
    joblib.dump(model, model_path)

    meta = {
        "version": version,
        "model_type": model_type,
        "feature_columns": FEATURE_COLUMNS,
        "trained_seasons": seasons,
        "n_training_rows": len(frame),
    }
    meta_path = out_dir / f"model_{version}.json"
    meta_path.write_text(json.dumps(meta, indent=2))

    logger.info("Saved model to %s", model_path)
    return meta


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the gridiron win-probability model")
    parser.add_argument("--seasons", type=int, nargs="+", required=True)
    parser.add_argument("--model-type", choices=MODEL_TYPES, default="logreg")
    parser.add_argument("--version", default=None, help="Defaults to '<model-type>_v1'")
    parser.add_argument("--model-dir", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    settings = get_settings()
    version = args.version or f"{args.model_type}_v1"
    model_dir = args.model_dir or settings.model_dir
    train(seasons=args.seasons, model_type=args.model_type, version=version, model_dir=model_dir)


if __name__ == "__main__":
    main(sys.argv[1:])
