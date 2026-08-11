"""Long-running loop for docker-compose: periodically re-ingests data and
regenerates predictions for the current season so the app stays current as
games are played, without any manual /ingest + /predict calls. Runs as its
own container/process (see the `scheduler` service in docker-compose.yml)
rather than inside the API process, so a slow refresh can't block requests.

Predictions themselves only ever depend on *prior*-season stats (see
ml/features.py), so re-running this doesn't change what a game's prediction
is — what it keeps current is which games have been played (scores) and
which upcoming games have predictions at all, as new weeks' schedules
solidify and new seasons roll over.
"""

from __future__ import annotations

import logging
import time

from sqlalchemy import func, select

from app.config import get_settings
from app.db import SessionLocal
from app.models import Game
from ml.ingest import run_ingest
from ml.predict import run_predict
from ml.season_config import current_nfl_season, default_schedule_years, default_stats_years

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("scheduler")

# Games are mostly played Thu/Sun/Mon, so daily is frequent enough to pick
# up new results promptly without hammering the upstream data source.
REFRESH_INTERVAL_SECONDS = 24 * 60 * 60
# If a refresh fails (upstream hiccup, or racing the API container's own
# first-boot bootstrap before a model file exists yet), retry sooner rather
# than waiting a full day.
RETRY_INTERVAL_SECONDS = 5 * 60


def _latest_ingested_season() -> int | None:
    with SessionLocal() as db:
        return db.scalar(select(func.max(Game.season)))


def refresh_once() -> None:
    settings = get_settings()
    logger.info("Refreshing data...")
    run_ingest(stats_years=default_stats_years(), schedule_years=default_schedule_years())

    season = _latest_ingested_season() or current_nfl_season()
    n = run_predict(
        version=settings.default_model_version, model_dir=settings.model_dir, season=season
    )
    logger.info("Refreshed predictions for season=%s (%d games)", season, n)


def main() -> None:
    while True:
        try:
            refresh_once()
            sleep_for = REFRESH_INTERVAL_SECONDS
        except Exception:
            logger.exception("Refresh failed, will retry sooner")
            sleep_for = RETRY_INTERVAL_SECONDS
        time.sleep(sleep_for)


if __name__ == "__main__":
    main()
