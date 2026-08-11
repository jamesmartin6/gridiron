from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Game, Prediction, SeasonStats, WeeklyTeamStats
from app.schemas import (
    FeatureBreakdown,
    GameDetailOut,
    GameOut,
    PredictResponse,
    SeasonStatsOut,
    WeeklyTeamStatsOut,
)

router = APIRouter(tags=["predictions"])


@router.get("/predictions/{game_id}", response_model=GameDetailOut)
def get_prediction(
    game_id: str,
    model_version: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> GameDetailOut:
    game = db.get(Game, game_id)
    if game is None:
        raise HTTPException(status_code=404, detail=f"No game with id {game_id}")

    settings = get_settings()
    version = model_version or settings.default_model_version
    stats_season = game.season - 1

    home_stats = db.get(SeasonStats, {"team_id": game.home_team, "season": stats_season})
    away_stats = db.get(SeasonStats, {"team_id": game.away_team, "season": stats_season})
    home_current = db.get(
        WeeklyTeamStats, {"team_id": game.home_team, "season": game.season, "week": game.week}
    )
    away_current = db.get(
        WeeklyTeamStats, {"team_id": game.away_team, "season": game.season, "week": game.week}
    )

    breakdown = None
    if home_stats is not None and away_stats is not None:
        from ml.features import blend_team_stats, feature_breakdown

        def _stat_dict(row) -> dict:
            return {
                "epa_offense": row.epa_offense,
                "epa_defense": row.epa_defense,
                "turnover_margin": row.turnover_margin,
                "win_pct": row.win_pct,
                "yards_per_play": row.yards_per_play,
            }

        home_blended = blend_team_stats(
            _stat_dict(home_stats),
            _stat_dict(home_current) if home_current else None,
            home_current.games_played if home_current else 0,
        )
        away_blended = blend_team_stats(
            _stat_dict(away_stats),
            _stat_dict(away_current) if away_current else None,
            away_current.games_played if away_current else 0,
        )
        breakdown = feature_breakdown(home_blended, away_blended)

    prediction = db.get(Prediction, {"game_id": game_id, "model_version": version})

    return GameDetailOut(
        game=GameOut.model_validate(game),
        home_stats=SeasonStatsOut.model_validate(home_stats) if home_stats else None,
        away_stats=SeasonStatsOut.model_validate(away_stats) if away_stats else None,
        stats_season=stats_season,
        home_current_stats=WeeklyTeamStatsOut.model_validate(home_current) if home_current else None,
        away_current_stats=WeeklyTeamStatsOut.model_validate(away_current) if away_current else None,
        feature_breakdown=FeatureBreakdown(**breakdown) if breakdown else None,
        prediction=prediction,
    )


@router.post("/predict", response_model=PredictResponse)
def trigger_predict(
    season: int = Query(...),
    week: int | None = Query(default=None),
    model_version: str | None = Query(default=None),
) -> PredictResponse:
    """Admin/internal: runs the current model over games for a season (or
    season+week) and writes results to the predictions table."""
    from ml.predict import run_predict

    settings = get_settings()
    version = model_version or settings.default_model_version
    n = run_predict(version=version, model_dir=settings.model_dir, season=season, week=week)
    return PredictResponse(model_version=version, season=season, week=week, n_predictions=n)
