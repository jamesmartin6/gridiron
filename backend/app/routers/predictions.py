from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Game, Prediction, SeasonStats
from app.schemas import (
    FeatureBreakdown,
    GameDetailOut,
    GameOut,
    PredictResponse,
    SeasonStatsOut,
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

    breakdown = None
    if home_stats is not None and away_stats is not None:
        from ml.features import feature_breakdown

        breakdown = feature_breakdown(
            {
                "epa_offense": home_stats.epa_offense,
                "epa_defense": home_stats.epa_defense,
                "turnover_margin": home_stats.turnover_margin,
                "win_pct": home_stats.win_pct,
                "yards_per_play": home_stats.yards_per_play,
            },
            {
                "epa_offense": away_stats.epa_offense,
                "epa_defense": away_stats.epa_defense,
                "turnover_margin": away_stats.turnover_margin,
                "win_pct": away_stats.win_pct,
                "yards_per_play": away_stats.yards_per_play,
            },
        )

    prediction = db.get(Prediction, {"game_id": game_id, "model_version": version})

    return GameDetailOut(
        game=GameOut.model_validate(game),
        home_stats=SeasonStatsOut.model_validate(home_stats) if home_stats else None,
        away_stats=SeasonStatsOut.model_validate(away_stats) if away_stats else None,
        stats_season=stats_season,
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
