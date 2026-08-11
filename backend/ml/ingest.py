"""Pulls NFL data via nfl_data_py and populates teams, season_stats, and games.

Why play-by-play instead of import_weekly_data for team stats: nfl_data_py's
weekly data is player-level offensive production only, with no defensive
counterpart, so team defensive EPA (a core feature) can't be derived from it.
Play-by-play data carries posteam/defteam on every row, which lets us compute
both sides of EPA, turnover margin, and yards/play correctly. Points and win
percentage still come from the schedules, matching the spec.
"""

from __future__ import annotations

import argparse
import logging
import math
import sys

import nfl_data_py as nfl
import pandas as pd
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db import Base, SessionLocal, engine
from app.models import Game, SeasonStats, Team, WeeklyTeamStats
from ml.season_config import default_schedule_years, default_stats_years, default_weekly_stats_years

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("ingest")

SCRIMMAGE_PLAY_TYPES = ("pass", "run")


def _grouped(frame: pd.DataFrame, key: str, value: str, agg: str, name: str) -> pd.Series:
    series = frame.dropna(subset=[value]).groupby([key, "season"])[value].agg(agg)
    series = series.rename(name)
    series.index = series.index.set_names(["team_id", "season"])
    return series


def fetch_team_metadata() -> pd.DataFrame:
    desc = nfl.import_team_desc()[["team_abbr", "team_name"]].drop_duplicates("team_abbr")
    desc = desc.rename(columns={"team_abbr": "team_id", "team_name": "name"})
    return desc.reset_index(drop=True)


def fetch_schedules(years: list[int]) -> pd.DataFrame:
    df = nfl.import_schedules(years)
    df = df[df["game_type"] == "REG"].copy()
    df["game_date"] = pd.to_datetime(df["gameday"], errors="coerce").dt.date
    return df[
        [
            "game_id",
            "season",
            "week",
            "home_team",
            "away_team",
            "home_score",
            "away_score",
            "game_date",
        ]
    ]


def fetch_pbp(years: list[int]) -> pd.DataFrame:
    """Fetches play-by-play once so callers needing multiple slices of it
    (season-level stats, week-by-week rolling stats) don't each re-pull the
    same seasons over the network — that redundant pull used to roughly
    double ingest time."""
    if not years:
        return pd.DataFrame()
    pbp = nfl.import_pbp_data(years, downcast=True, cache=False)
    return pbp[pbp["season_type"] == "REG"]


def compute_season_stats(years: list[int], pbp: pd.DataFrame | None = None) -> pd.DataFrame:
    if not years:
        return pd.DataFrame(
            columns=[
                "team_id",
                "season",
                "points_for",
                "points_against",
                "epa_offense",
                "epa_defense",
                "turnover_margin",
                "yards_per_play",
                "win_pct",
            ]
        )

    schedules = fetch_schedules(years)
    points = _compute_points_and_win_pct(schedules)

    if pbp is None:
        pbp = fetch_pbp(years)
    pbp = pbp[pbp["season"].isin(years)]
    scrimmage = pbp[pbp["play_type"].isin(SCRIMMAGE_PLAY_TYPES)]

    stats = _aggregate_pbp_stats(scrimmage, pbp)
    stats = stats.merge(points, on=["team_id", "season"], how="outer")
    # turnover_margin starts as a season total; convert to a per-game rate so
    # it's on the same footing as the other rate stats (needed to blend
    # cleanly with in-season-to-date stats, which cover fewer games).
    stats["turnover_margin"] = stats["turnover_margin"] / stats["games_played"]
    return stats.drop(columns=["games_played"])


def _aggregate_pbp_stats(scrimmage: pd.DataFrame, pbp: pd.DataFrame) -> pd.DataFrame:
    """Given scrimmage plays and all plays (both already filtered to the
    rows that should count, e.g. REG season and/or week < cutoff), return
    one row per team/season with epa_offense, epa_defense, yards_per_play,
    and a *total* turnover_margin (caller converts to a rate if needed)."""
    off_epa = _grouped(scrimmage, "posteam", "epa", "mean", "epa_offense")
    def_epa = _grouped(scrimmage, "defteam", "epa", "mean", "epa_defense")
    ypp = _grouped(scrimmage, "posteam", "yards_gained", "mean", "yards_per_play")

    turnovers = pbp.copy()
    turnovers["is_turnover"] = (
        turnovers["interception"].fillna(0) + turnovers["fumble_lost"].fillna(0)
    ).clip(upper=1)
    giveaways = _grouped(turnovers, "posteam", "is_turnover", "sum", "giveaways")
    takeaways = _grouped(turnovers, "defteam", "is_turnover", "sum", "takeaways")

    stats = (
        off_epa.to_frame()
        .join(def_epa, how="outer")
        .join(ypp, how="outer")
        .join(giveaways, how="outer")
        .join(takeaways, how="outer")
    )
    stats = stats.reset_index()
    stats["turnover_margin"] = stats["takeaways"].fillna(0) - stats["giveaways"].fillna(0)
    return stats.drop(columns=["giveaways", "takeaways"])


WEEKLY_STATS_COLUMNS = [
    "team_id",
    "season",
    "week",
    "games_played",
    "points_for",
    "points_against",
    "epa_offense",
    "epa_defense",
    "turnover_margin",
    "yards_per_play",
    "win_pct",
]


def compute_weekly_rolling_stats(years: list[int], pbp: pd.DataFrame | None = None) -> pd.DataFrame:
    """For every team/season/week, stats accumulated from that team's games
    strictly BEFORE that week within the same season (i.e. "as of" the start
    of the week). Week 1 always has games_played=0 (nothing to roll up yet)
    — features.py treats that as "no in-season data available", falling
    back to pure prior-season stats.
    """
    if not years:
        return pd.DataFrame(columns=WEEKLY_STATS_COLUMNS)

    schedules = fetch_schedules(years)
    if pbp is None:
        pbp = fetch_pbp(years)
    pbp = pbp[pbp["season"].isin(years)]
    scrimmage = pbp[pbp["play_type"].isin(SCRIMMAGE_PLAY_TYPES)]

    frames = []
    for season in years:
        season_sched = schedules[schedules["season"] == season]
        season_pbp = pbp[pbp["season"] == season]
        season_scrimmage = scrimmage[scrimmage["season"] == season]
        weeks = sorted(int(w) for w in season_sched["week"].dropna().unique())
        teams = sorted(pd.unique(season_sched[["home_team", "away_team"]].values.ravel()))

        for week in weeks:
            base = pd.DataFrame({"team_id": teams})
            base["season"] = season
            base["week"] = week

            prior_sched = season_sched[season_sched["week"] < week]
            prior_played = prior_sched.dropna(subset=["home_score", "away_score"])
            if prior_played.empty:
                base["games_played"] = 0
                for col in WEEKLY_STATS_COLUMNS:
                    if col not in base.columns:
                        base[col] = float("nan")
                frames.append(base[WEEKLY_STATS_COLUMNS])
                continue

            points = _compute_points_and_win_pct(prior_played)
            prior_pbp = season_pbp[season_pbp["week"] < week]
            prior_scrimmage = season_scrimmage[season_scrimmage["week"] < week]
            pbp_stats = _aggregate_pbp_stats(prior_scrimmage, prior_pbp)

            merged = base.merge(points, on=["team_id", "season"], how="left")
            merged = merged.merge(pbp_stats, on=["team_id", "season"], how="left")
            merged["games_played"] = merged["games_played"].astype(float).fillna(0)
            merged["turnover_margin"] = merged["turnover_margin"] / merged["games_played"].replace(
                0, float("nan")
            )
            frames.append(merged[WEEKLY_STATS_COLUMNS])

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=WEEKLY_STATS_COLUMNS)


def _compute_points_and_win_pct(schedules: pd.DataFrame) -> pd.DataFrame:
    played = schedules.dropna(subset=["home_score", "away_score"]).copy()

    home = played.rename(
        columns={
            "home_team": "team_id",
            "home_score": "points_for",
            "away_score": "points_against",
        }
    )[["team_id", "season", "points_for", "points_against"]]
    home["win"] = (played["home_score"] > played["away_score"]).astype(float)
    home["tie"] = (played["home_score"] == played["away_score"]).astype(float)

    away = played.rename(
        columns={
            "away_team": "team_id",
            "away_score": "points_for",
            "home_score": "points_against",
        }
    )[["team_id", "season", "points_for", "points_against"]]
    away["win"] = (played["away_score"] > played["home_score"]).astype(float)
    away["tie"] = (played["home_score"] == played["away_score"]).astype(float)

    both = pd.concat([home, away], ignore_index=True)
    both["win_credit"] = both["win"] + 0.5 * both["tie"]

    grouped = both.groupby(["team_id", "season"]).agg(
        points_for=("points_for", "sum"),
        points_against=("points_against", "sum"),
        win_credit=("win_credit", "sum"),
        games_played=("win", "count"),
    )
    grouped["win_pct"] = grouped["win_credit"] / grouped["games_played"]
    return grouped.drop(columns=["win_credit"]).reset_index()


def _records_with_none(df: pd.DataFrame) -> list[dict]:
    """pandas keeps NaN (not None) in numeric columns even after .where(),
    since a float64 column can't hold Python None, and psycopg2 sends NaN as
    a literal float that overflows integer columns. Scrub it row-by-row."""
    records = df.to_dict("records")
    for row in records:
        for key, value in row.items():
            if isinstance(value, float) and math.isnan(value):
                row[key] = None
    return records


def upsert_teams(db: Session, teams: pd.DataFrame) -> int:
    if teams.empty:
        return 0
    rows = teams.to_dict("records")
    stmt = pg_insert(Team).values(rows)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Team.team_id], set_={"name": stmt.excluded.name}
    )
    db.execute(stmt)
    return len(rows)


def upsert_season_stats(db: Session, stats: pd.DataFrame) -> int:
    if stats.empty:
        return 0
    rows = _records_with_none(stats)
    stmt = pg_insert(SeasonStats).values(rows)
    update_cols = {
        c: stmt.excluded[c]
        for c in (
            "points_for",
            "points_against",
            "epa_offense",
            "epa_defense",
            "turnover_margin",
            "yards_per_play",
            "win_pct",
        )
    }
    stmt = stmt.on_conflict_do_update(
        index_elements=[SeasonStats.team_id, SeasonStats.season], set_=update_cols
    )
    db.execute(stmt)
    return len(rows)


def upsert_weekly_team_stats(db: Session, stats: pd.DataFrame) -> int:
    if stats.empty:
        return 0
    rows = _records_with_none(stats)
    stmt = pg_insert(WeeklyTeamStats).values(rows)
    update_cols = {
        c: stmt.excluded[c]
        for c in (
            "games_played",
            "points_for",
            "points_against",
            "epa_offense",
            "epa_defense",
            "turnover_margin",
            "yards_per_play",
            "win_pct",
        )
    }
    stmt = stmt.on_conflict_do_update(
        index_elements=[WeeklyTeamStats.team_id, WeeklyTeamStats.season, WeeklyTeamStats.week],
        set_=update_cols,
    )
    db.execute(stmt)
    return len(rows)


def upsert_games(db: Session, games: pd.DataFrame) -> int:
    if games.empty:
        return 0
    rows = _records_with_none(games)
    stmt = pg_insert(Game).values(rows)
    update_cols = {
        c: stmt.excluded[c]
        for c in ("season", "week", "home_team", "away_team", "home_score", "away_score", "game_date")
    }
    stmt = stmt.on_conflict_do_update(index_elements=[Game.game_id], set_=update_cols)
    db.execute(stmt)
    return len(rows)


def run_ingest(
    stats_years: list[int],
    schedule_years: list[int],
    weekly_stats_years: list[int] | None = None,
) -> dict:
    Base.metadata.create_all(engine)
    if weekly_stats_years is None:
        weekly_stats_years = default_weekly_stats_years()

    logger.info("Fetching team metadata")
    teams = fetch_team_metadata()

    logger.info("Fetching schedules for seasons: %s", schedule_years)
    schedules = fetch_schedules(schedule_years)

    pbp_years = sorted(set(stats_years) | set(weekly_stats_years))
    logger.info("Fetching play-by-play for seasons: %s", pbp_years)
    pbp = fetch_pbp(pbp_years)

    logger.info("Computing season stats for seasons: %s", stats_years)
    stats = compute_season_stats(stats_years, pbp)

    logger.info("Computing in-season weekly rolling stats for seasons: %s", weekly_stats_years)
    weekly_stats = compute_weekly_rolling_stats(weekly_stats_years, pbp)

    with SessionLocal() as db:
        n_teams = upsert_teams(db, teams)
        n_games = upsert_games(db, schedules)
        n_stats = upsert_season_stats(db, stats)
        n_weekly = upsert_weekly_team_stats(db, weekly_stats)
        db.commit()

    summary = {
        "teams": n_teams,
        "games": n_games,
        "season_stats": n_stats,
        "weekly_team_stats": n_weekly,
    }
    logger.info("Ingest complete: %s", summary)
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest NFL data into the gridiron database")
    parser.add_argument(
        "--stats-seasons",
        type=int,
        nargs="+",
        default=default_stats_years(),
        help="Seasons to compute season_stats for (needs completed games).",
    )
    parser.add_argument(
        "--schedule-seasons",
        type=int,
        nargs="+",
        default=default_schedule_years(),
        help="Seasons to load into the games table (may include upcoming/unplayed seasons).",
    )
    parser.add_argument(
        "--weekly-stats-seasons",
        type=int,
        nargs="+",
        default=default_weekly_stats_years(),
        help="Seasons to compute in-season (week-by-week) rolling stats for.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    run_ingest(
        stats_years=args.stats_seasons,
        schedule_years=args.schedule_seasons,
        weekly_stats_years=args.weekly_stats_seasons,
    )


if __name__ == "__main__":
    main(sys.argv[1:])
