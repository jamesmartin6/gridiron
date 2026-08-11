"""Shared season-range helpers so ingest/bootstrap/scheduler don't need
hardcoded year lists that go stale every year.
"""

from __future__ import annotations

import datetime as dt

DATA_START_YEAR = 2018


def current_nfl_season(today: dt.date | None = None) -> int:
    """NFL seasons are named for the year they start (games played in
    Jan/Feb belong to the season that started the previous fall), so treat
    Jan/Feb as still part of the previous season."""
    today = today or dt.date.today()
    return today.year if today.month >= 3 else today.year - 1


def default_stats_years(today: dt.date | None = None) -> list[int]:
    """Seasons with completed games, safe to compute season_stats for."""
    return list(range(DATA_START_YEAR, current_nfl_season(today)))


def default_schedule_years(today: dt.date | None = None) -> list[int]:
    """Seasons to keep in the games table, including the current (possibly
    not-yet-played) season's schedule."""
    return list(range(DATA_START_YEAR, current_nfl_season(today) + 1))


def default_weekly_stats_years(today: dt.date | None = None) -> list[int]:
    """Seasons to compute in-season (week-by-week, as-of) rolling stats for.
    A season's weekly stats only ever depend on that same season's earlier
    games (never a prior season), so unlike default_stats_years this only
    needs to cover seasons that are actually trained/backtested/predicted on
    — which starts two years into the data window, same as
    default_train_seasons — but unlike that one, it MUST include the
    current season: that's what lets this season's results-so-far influence
    this season's predictions."""
    return list(range(DATA_START_YEAR + 2, current_nfl_season(today) + 1))


def default_train_seasons(today: dt.date | None = None) -> list[int]:
    """Seasons with usable prior-season stats for training. Starts two years
    into the data window rather than one, to steer clear of edge cases from
    franchise relocations right at the boundary (e.g. Oakland -> Las Vegas)
    where a team's prior-season stats exist under a different team_id."""
    return list(range(DATA_START_YEAR + 2, current_nfl_season(today)))


def default_backtest_seasons(today: dt.date | None = None) -> list[int]:
    """The three most recent completed seasons."""
    season = current_nfl_season(today)
    return [season - 3, season - 2, season - 1]
