from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import BacktestResult
from app.schemas import BacktestResultOut

router = APIRouter(prefix="/backtest", tags=["backtest"])


@router.get("", response_model=list[BacktestResultOut])
def list_backtest_results(
    model_version: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[BacktestResult]:
    stmt = select(BacktestResult).order_by(
        BacktestResult.model_version, BacktestResult.test_season
    )
    if model_version:
        stmt = stmt.where(BacktestResult.model_version == model_version)
    return list(db.scalars(stmt))
