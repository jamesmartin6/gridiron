"""Builds model feature vectors from team stats.

Every game is featurized from a *blend* of two things, per team:

1. The team's full prior-season stats (season N-1 for a season-N game) —
   this is the only signal available before the season starts, and stays
   the anchor for early-season games.
2. The team's current-season stats *to date* (games strictly before the one
   being predicted) — as the season progresses this makes up more and more
   of the blend, which is what lets in-season results actually move
   predictions instead of every week's prediction for a matchup being
   identical.

The blend is a shrinkage estimator, not a learned parameter: weight shifts
from the prior season toward the current season as games_played grows,
treating the entire prior season as worth PRIOR_SEASON_SHRINKAGE_GAMES
current-season-equivalent games of evidence. At games_played=0 (week 1, or
whenever current-season data isn't available) it's mathematically identical
to using the prior season alone — so this is a strict generalization of the
original prior-season-only approach, not a replacement for it.

Games where a team has no prior-season stats at all (e.g. the edge of the
data window) are still dropped from training/eval, same as before — a
missing prior season can't be compensated for by blending.
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

# How many current-season games it takes for current-season form to carry as
# much weight as the ENTIRE prior season combined. Lower = current season
# matters sooner. 6 means the blend is already past 50/50 by the team's 7th
# game of the season (~week 8-9 accounting for a bye), which is early enough
# to matter for a full-season view without overreacting to a 1-2 game sample.
PRIOR_SEASON_SHRINKAGE_GAMES = 6


def _blend_series(prior: pd.Series, current: pd.Series, games_played: pd.Series) -> pd.Series:
    prior = prior.astype(float)
    current = current.astype(float)
    games_played = games_played.astype(float)
    weight_current = games_played / (games_played + PRIOR_SEASON_SHRINKAGE_GAMES)
    # current.fillna(prior) makes weight_current * current well-defined (not
    # NaN) even when there's no current-season data yet, since games_played
    # is 0 in exactly that case and the weighted term should vanish anyway.
    return weight_current * current.fillna(prior) + (1 - weight_current) * prior


def build_feature_frame(
    games: pd.DataFrame,
    season_stats: pd.DataFrame,
    weekly_team_stats: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Join games to prior-season and current-season-to-date stats for both
    teams, blend them, and compute diffs.

    Parameters
    ----------
    games: columns game_id, season, week, home_team, away_team, home_score, away_score
    season_stats: columns team_id, season, + STAT_COLUMNS (prior-season stats)
    weekly_team_stats: columns team_id, season, week, games_played, +
        STAT_COLUMNS (each team's stats as of before that week, within the
        same season). Optional — omitting it (or passing an empty frame)
        falls back to pure prior-season stats, identical to the original
        behavior before in-season blending existed.

    Returns a frame with game_id, season, week, home_team, away_team,
    DIFF_FEATURE_COLUMNS, home_flag, and home_team_won (only present when
    both scores are known).
    """
    stats = season_stats[["team_id", "season", *STAT_COLUMNS]].copy()
    # A stats row from `season` is the "prior season" for games played the
    # following year, i.e. it applies as a feature to games in `season + 1`.
    stats["applies_to_season"] = stats["season"] + 1

    df = games.copy()

    home_prior = stats.rename(columns={c: f"home_prior_{c}" for c in STAT_COLUMNS})
    home_prior = home_prior.rename(columns={"team_id": "home_team"})
    away_prior = stats.rename(columns={c: f"away_prior_{c}" for c in STAT_COLUMNS})
    away_prior = away_prior.rename(columns={"team_id": "away_team"})

    df = df.merge(
        home_prior[["home_team", "applies_to_season", *[f"home_prior_{c}" for c in STAT_COLUMNS]]],
        left_on=["home_team", "season"],
        right_on=["home_team", "applies_to_season"],
        how="left",
    )
    df = df.merge(
        away_prior[["away_team", "applies_to_season", *[f"away_prior_{c}" for c in STAT_COLUMNS]]],
        left_on=["away_team", "season"],
        right_on=["away_team", "applies_to_season"],
        how="left",
    )

    if weekly_team_stats is None or weekly_team_stats.empty:
        weekly = pd.DataFrame(columns=["team_id", "season", "week", "games_played", *STAT_COLUMNS])
    else:
        weekly = weekly_team_stats[["team_id", "season", "week", "games_played", *STAT_COLUMNS]].copy()

    home_current = weekly.rename(columns={c: f"home_current_{c}" for c in STAT_COLUMNS})
    home_current = home_current.rename(
        columns={"team_id": "home_team", "games_played": "home_games_played"}
    )
    away_current = weekly.rename(columns={c: f"away_current_{c}" for c in STAT_COLUMNS})
    away_current = away_current.rename(
        columns={"team_id": "away_team", "games_played": "away_games_played"}
    )

    df = df.merge(
        home_current[
            ["home_team", "season", "week", "home_games_played", *[f"home_current_{c}" for c in STAT_COLUMNS]]
        ],
        on=["home_team", "season", "week"],
        how="left",
    )
    df = df.merge(
        away_current[
            ["away_team", "season", "week", "away_games_played", *[f"away_current_{c}" for c in STAT_COLUMNS]]
        ],
        on=["away_team", "season", "week"],
        how="left",
    )
    df["home_games_played"] = df["home_games_played"].astype(float).fillna(0)
    df["away_games_played"] = df["away_games_played"].astype(float).fillna(0)

    for c in STAT_COLUMNS:
        df[f"home_{c}"] = _blend_series(
            df[f"home_prior_{c}"], df[f"home_current_{c}"], df["home_games_played"]
        )
        df[f"away_{c}"] = _blend_series(
            df[f"away_prior_{c}"], df[f"away_current_{c}"], df["away_games_played"]
        )
        df[f"{c}_diff"] = df[f"home_{c}"] - df[f"away_{c}"]

    df["home_flag"] = 1

    # A team must have SOME prior-season baseline to be included at all —
    # in-season data only ever supplements that, it can't substitute for it.
    required = [f"home_prior_{c}" for c in STAT_COLUMNS] + [f"away_prior_{c}" for c in STAT_COLUMNS]
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


def blend_team_stats(prior: dict, current: dict | None, games_played: int) -> dict:
    """Scalar equivalent of _blend_series, for single-game API use (the game
    detail page's feature breakdown) where there's no DataFrame to vectorize
    over. Must stay behaviorally identical to _blend_series."""
    weight_current = games_played / (games_played + PRIOR_SEASON_SHRINKAGE_GAMES)
    blended = {}
    for c in STAT_COLUMNS:
        prior_val = prior.get(c)
        if prior_val is None:
            blended[c] = None
            continue
        current_val = (current or {}).get(c)
        if current_val is None or games_played == 0:
            blended[c] = float(prior_val)
        else:
            blended[c] = weight_current * float(current_val) + (1 - weight_current) * float(prior_val)
    return blended


def feature_breakdown(home_stats: dict, away_stats: dict) -> dict:
    """Per-feature home-minus-away diffs for a single game (API/detail view).
    Pass already-blended stats (see blend_team_stats) for the breakdown to
    reflect in-season form the same way training/prediction do."""
    return {
        f"{c}_diff": (
            None
            if home_stats.get(c) is None or away_stats.get(c) is None
            else float(home_stats[c]) - float(away_stats[c])
        )
        for c in STAT_COLUMNS
    }
