from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import SeasonStats, Team
from app.schemas import SeasonStatsOut, TeamOut

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("", response_model=list[TeamOut])
def list_teams(db: Session = Depends(get_db)) -> list[Team]:
    return list(db.scalars(select(Team).order_by(Team.team_id)))


@router.get("/{team_id}/stats", response_model=SeasonStatsOut)
def get_team_stats(
    team_id: str, season: int, db: Session = Depends(get_db)
) -> SeasonStats:
    team_id = team_id.upper()
    stats = db.get(SeasonStats, {"team_id": team_id, "season": season})
    if stats is None:
        raise HTTPException(
            status_code=404,
            detail=f"No stats for team_id={team_id} season={season}",
        )
    return stats
