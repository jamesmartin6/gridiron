from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Game, Prediction
from app.schemas import GameOut, IngestResponse, PredictionOut

router = APIRouter(tags=["games"])


def _resolve_default_season(db: Session) -> int | None:
    return db.scalar(select(func.max(Game.season)))


def _resolve_default_week(db: Session, season: int) -> int:
    upcoming = db.scalar(
        select(func.min(Game.week)).where(
            Game.season == season, Game.home_score.is_(None)
        )
    )
    if upcoming is not None:
        return upcoming
    latest_played = db.scalar(
        select(func.max(Game.week)).where(
            Game.season == season, Game.home_score.is_not(None)
        )
    )
    return latest_played or 1


@router.get("/games", response_model=list[GameOut])
def list_games(
    season: int | None = Query(default=None),
    week: int | None = Query(default=None),
    model_version: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[GameOut]:
    settings = get_settings()
    version = model_version or settings.default_model_version

    if season is None:
        season = _resolve_default_season(db)
    if season is None:
        return []
    if week is None:
        week = _resolve_default_week(db, season)

    games = list(
        db.scalars(
            select(Game)
            .where(Game.season == season, Game.week == week)
            .order_by(Game.game_id)
        )
    )
    if not games:
        return []

    game_ids = [g.game_id for g in games]
    preds = {
        p.game_id: p
        for p in db.scalars(
            select(Prediction).where(
                Prediction.model_version == version, Prediction.game_id.in_(game_ids)
            )
        )
    }

    result = []
    for g in games:
        pred = preds.get(g.game_id)
        game_out = GameOut.model_validate(g)
        game_out.prediction = PredictionOut.model_validate(pred) if pred else None
        result.append(game_out)
    return result


@router.post("/ingest", response_model=IngestResponse)
def trigger_ingest(
    stats_seasons: list[int] | None = Query(default=None),
    schedule_seasons: list[int] | None = Query(default=None),
    weekly_stats_seasons: list[int] | None = Query(default=None),
) -> IngestResponse:
    """Admin/internal: pulls fresh data via nfl_data_py and refreshes
    teams, season_stats, games, and weekly_team_stats. Synchronous — can
    take a couple of minutes (weekly_team_stats is the slow part)."""
    from ml.ingest import run_ingest
    from ml.season_config import (
        default_schedule_years,
        default_stats_years,
        default_weekly_stats_years,
    )

    stats_years = stats_seasons or default_stats_years()
    schedule_years = schedule_seasons or default_schedule_years()
    weekly_years = weekly_stats_seasons or default_weekly_stats_years()
    summary = run_ingest(
        stats_years=stats_years, schedule_years=schedule_years, weekly_stats_years=weekly_years
    )
    return IngestResponse(**summary)
