from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Team(Base):
    __tablename__ = "teams"

    team_id: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)

    season_stats: Mapped[list["SeasonStats"]] = relationship(back_populates="team")


class SeasonStats(Base):
    __tablename__ = "season_stats"

    team_id: Mapped[str] = mapped_column(ForeignKey("teams.team_id"), primary_key=True)
    season: Mapped[int] = mapped_column(primary_key=True)
    points_for: Mapped[float | None] = mapped_column(Numeric)
    points_against: Mapped[float | None] = mapped_column(Numeric)
    epa_offense: Mapped[float | None] = mapped_column(Numeric)
    epa_defense: Mapped[float | None] = mapped_column(Numeric)
    turnover_margin: Mapped[float | None] = mapped_column(Numeric)
    yards_per_play: Mapped[float | None] = mapped_column(Numeric)
    win_pct: Mapped[float | None] = mapped_column(Numeric)

    team: Mapped["Team"] = relationship(back_populates="season_stats")


class Game(Base):
    __tablename__ = "games"

    game_id: Mapped[str] = mapped_column(primary_key=True)
    season: Mapped[int] = mapped_column(nullable=False)
    week: Mapped[int] = mapped_column(nullable=False)
    home_team: Mapped[str] = mapped_column(ForeignKey("teams.team_id"))
    away_team: Mapped[str] = mapped_column(ForeignKey("teams.team_id"))
    home_score: Mapped[int | None]
    away_score: Mapped[int | None]
    game_date: Mapped[date | None] = mapped_column(Date)

    predictions: Mapped[list["Prediction"]] = relationship(back_populates="game")


class Prediction(Base):
    __tablename__ = "predictions"

    game_id: Mapped[str] = mapped_column(ForeignKey("games.game_id"), primary_key=True)
    model_version: Mapped[str] = mapped_column(primary_key=True)
    home_win_prob: Mapped[float] = mapped_column(Numeric, nullable=False)
    predicted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    game: Mapped["Game"] = relationship(back_populates="predictions")


class BacktestResult(Base):
    __tablename__ = "backtest_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    model_version: Mapped[str] = mapped_column(nullable=False)
    test_season: Mapped[int] = mapped_column(nullable=False)
    accuracy: Mapped[float | None] = mapped_column(Numeric)
    log_loss: Mapped[float | None] = mapped_column(Numeric)
    brier_score: Mapped[float | None] = mapped_column(Numeric)
    baseline_accuracy: Mapped[float | None] = mapped_column(Numeric)
    n_games: Mapped[int | None]
    run_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
