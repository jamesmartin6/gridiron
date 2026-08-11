"""Deterministic synthetic multi-season data for tests that need a full
teams/season_stats/games dataset (training, backtesting, API) without
depending on the network or real nfl_data_py data.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Game, SeasonStats, Team

TEAM_IDS = ["AAA", "BBB", "CCC", "DDD"]
# Deliberately uneven strength so features carry real signal.
STRENGTH = {"AAA": 0.75, "BBB": 0.60, "CCC": 0.40, "DDD": 0.25}
SEASONS_WITH_STATS = [2020, 2021, 2022]
SEASONS_WITH_GAMES = [2021, 2022, 2023]  # each uses the season before it as "prior"


def seed_multi_season_data(db: Session) -> None:
    for team_id in TEAM_IDS:
        db.add(Team(team_id=team_id, name=f"{team_id} Test Team"))

    for season in SEASONS_WITH_STATS:
        for team_id in TEAM_IDS:
            strength = STRENGTH[team_id]
            db.add(
                SeasonStats(
                    team_id=team_id,
                    season=season,
                    points_for=300 + strength * 100,
                    points_against=300 - strength * 100,
                    epa_offense=(strength - 0.5) * 0.4,
                    epa_defense=(0.5 - strength) * 0.3,
                    turnover_margin=(strength - 0.5) * 10,
                    yards_per_play=5.0 + (strength - 0.5) * 2,
                    win_pct=strength,
                )
            )
    db.flush()

    game_idx = 0
    for season in SEASONS_WITH_GAMES:
        for i, home in enumerate(TEAM_IDS):
            for j, away in enumerate(TEAM_IDS):
                if home == away:
                    continue
                game_idx += 1
                # Deterministic "outcome": higher strength + slight home
                # edge wins, with the margin alternating so both classes
                # (and some closer games) appear across the schedule.
                home_edge = 0.03
                home_strength = STRENGTH[home] + home_edge
                away_strength = STRENGTH[away]
                home_wins = home_strength >= away_strength
                home_score = 24 if home_wins else 17
                away_score = 17 if home_wins else 24
                db.add(
                    Game(
                        game_id=f"{season}_{game_idx:03d}_{home}_{away}",
                        season=season,
                        week=(game_idx % 18) + 1,
                        home_team=home,
                        away_team=away,
                        home_score=home_score,
                        away_score=away_score,
                    )
                )
    db.commit()


def add_unplayed_game(db: Session, season: int, week: int, home: str, away: str) -> str:
    game_id = f"{season}_{week:03d}_{home}_{away}_upcoming"
    db.add(
        Game(
            game_id=game_id,
            season=season,
            week=week,
            home_team=home,
            away_team=away,
            home_score=None,
            away_score=None,
        )
    )
    db.commit()
    return game_id
