"""Builds model feature vectors from prior-season team stats.

Every game in season N is featurized using both teams' season N-1 stats, so
the model only ever sees information that would have been available before
the game was played. Games where either team lacks prior-season stats
(expansion into the data window, or a franchise's first tracked season) are
dropped.
"""

from __future__ import annotations

import pandas as pd

STAT_COLUMNS = [
    "epa_offense",
    "epa_defense",
    "turnover_margin",
    "win_pct",
    "yards_per_play",
]

DIFF_FEATURE_COLUMNS = [
    "epa_offense_diff",
    "epa_defense_diff",
    "turnover_margin_diff",
    "win_pct_diff",
    "yards_per_play_diff",
]

FEATURE_COLUMNS = [*DIFF_FEATURE_COLUMNS, "home_flag"]

LABEL_COLUMN = "home_team_won"


def build_feature_frame(games: pd.DataFrame, season_stats: pd.DataFrame) -> pd.DataFrame:
    """Join games to prior-season stats for both teams and compute diffs.

    Parameters
    ----------
    games: columns game_id, season, week, home_team, away_team, home_score, away_score
    season_stats: columns team_id, season, epa_offense, epa_defense,
        turnover_margin, win_pct, yards_per_play (+ optionally points_for/against)

    Returns a frame with game_id, season, week, home_team, away_team,
    DIFF_FEATURE_COLUMNS, home_flag, and home_team_won (only present when
    both scores are known).
    """
    stats = season_stats[["team_id", "season", *STAT_COLUMNS]].copy()
    stats["prior_season"] = stats["season"] + 1

    df = games.copy()
    df["prior_season"] = df["season"] - 1

    home_stats = stats.rename(columns={c: f"home_{c}" for c in STAT_COLUMNS})
    home_stats = home_stats.rename(columns={"team_id": "home_team"})
    away_stats = stats.rename(columns={c: f"away_{c}" for c in STAT_COLUMNS})
    away_stats = away_stats.rename(columns={"team_id": "away_team"})

    df = df.merge(
        home_stats[["home_team", "prior_season", *[f"home_{c}" for c in STAT_COLUMNS]]],
        on=["home_team", "prior_season"],
        how="left",
    )
    df = df.merge(
        away_stats[["away_team", "prior_season", *[f"away_{c}" for c in STAT_COLUMNS]]],
        on=["away_team", "prior_season"],
        how="left",
    )

    for c in STAT_COLUMNS:
        df[f"{c}_diff"] = df[f"home_{c}"] - df[f"away_{c}"]

    df["home_flag"] = 1

    required = [f"home_{c}" for c in STAT_COLUMNS] + [f"away_{c}" for c in STAT_COLUMNS]
    df = df.dropna(subset=required).reset_index(drop=True)

    has_scores = df["home_score"].notna() & df["away_score"].notna()
    df.loc[has_scores, LABEL_COLUMN] = (
        df.loc[has_scores, "home_score"] > df.loc[has_scores, "away_score"]
    ).astype(int)

    keep = [
        "game_id",
        "season",
        "week",
        "home_team",
        "away_team",
        *DIFF_FEATURE_COLUMNS,
        "home_flag",
        LABEL_COLUMN,
    ]
    return df[keep]


def feature_breakdown(home_stats: dict, away_stats: dict) -> dict:
    """Per-feature home-minus-away diffs for a single game (API/detail view)."""
    return {
        f"{c}_diff": (
            None
            if home_stats.get(c) is None or away_stats.get(c) is None
            else float(home_stats[c]) - float(away_stats[c])
        )
        for c in STAT_COLUMNS
    }
