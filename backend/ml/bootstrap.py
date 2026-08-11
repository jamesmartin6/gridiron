"""First-run bootstrap for docker-compose: if the database has no season
stats yet, pulls data, trains the default model, backtests it, and predicts
the current season's games. Safe to run on every container start — it's a
no-op once data exists, so restarting the stack doesn't re-pull/re-train.
"""

from __future__ import annotations

import logging

from app.config import get_settings
from app.db import Base, SessionLocal, engine
from app.models import SeasonStats
from ml.backtest import run_backtest
from ml.ingest import run_ingest
from ml.predict import run_predict
from ml.season_config import (
    current_nfl_season,
    default_backtest_seasons,
    default_schedule_years,
    default_stats_years,
    default_train_seasons,
)
from ml.train import train

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("bootstrap")


def has_data() -> bool:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        return db.query(SeasonStats).first() is not None


def main() -> None:
    if has_data():
        logger.info("season_stats already populated, skipping bootstrap")
        return

    settings = get_settings()
    logger.info("No data found, running first-time bootstrap (~1-2 minutes)")

    run_ingest(stats_years=default_stats_years(), schedule_years=default_schedule_years())
    train(
        seasons=default_train_seasons(),
        model_type="logreg",
        version=settings.default_model_version,
        model_dir=settings.model_dir,
    )
    run_backtest(
        seasons=default_backtest_seasons(), model_type="logreg", model_dir=settings.model_dir
    )
    run_predict(
        version=settings.default_model_version,
        model_dir=settings.model_dir,
        season=current_nfl_season(),
    )

    logger.info("Bootstrap complete")


if __name__ == "__main__":
    main()
