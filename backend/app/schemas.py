from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class TeamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    team_id: str
    name: str


class SeasonStatsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    team_id: str
    season: int
    points_for: float | None
    points_against: float | None
    epa_offense: float | None
    epa_defense: float | None
    turnover_margin: float | None
    yards_per_play: float | None
    win_pct: float | None


class WeeklyTeamStatsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    team_id: str
    season: int
    week: int
    games_played: int
    points_for: float | None
    points_against: float | None
    epa_offense: float | None
    epa_defense: float | None
    turnover_margin: float | None
    yards_per_play: float | None
    win_pct: float | None


class PredictionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    model_version: str
    home_win_prob: float
    predicted_at: datetime


class GameOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    game_id: str
    season: int
    week: int
    home_team: str
    away_team: str
    home_score: int | None
    away_score: int | None
    game_date: date | None
    prediction: PredictionOut | None = None


class FeatureBreakdown(BaseModel):
    epa_offense_diff: float | None
    epa_defense_diff: float | None
    turnover_margin_diff: float | None
    win_pct_diff: float | None
    yards_per_play_diff: float | None


class GameDetailOut(BaseModel):
    game: GameOut
    home_stats: SeasonStatsOut | None
    away_stats: SeasonStatsOut | None
    stats_season: int
    home_current_stats: WeeklyTeamStatsOut | None = None
    away_current_stats: WeeklyTeamStatsOut | None = None
    feature_breakdown: FeatureBreakdown | None
    prediction: PredictionOut | None


class BacktestResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    model_version: str
    test_season: int
    accuracy: float | None
    log_loss: float | None
    brier_score: float | None
    baseline_accuracy: float | None
    n_games: int | None
    run_at: datetime


class IngestResponse(BaseModel):
    teams: int
    games: int
    season_stats: int
    weekly_team_stats: int


class PredictResponse(BaseModel):
    model_version: str
    season: int
    week: int | None
    n_predictions: int
