import pandas as pd

from ml.features import (
    DIFF_FEATURE_COLUMNS,
    PRIOR_SEASON_SHRINKAGE_GAMES,
    blend_team_stats,
    build_feature_frame,
    feature_breakdown,
)


def _season_stats_row(team_id, season, **overrides):
    row = {
        "team_id": team_id,
        "season": season,
        "epa_offense": 0.0,
        "epa_defense": 0.0,
        "turnover_margin": 0.0,
        "win_pct": 0.5,
        "yards_per_play": 5.0,
        "points_for": 300,
        "points_against": 300,
    }
    row.update(overrides)
    return row


def test_build_feature_frame_computes_diffs_and_label():
    games = pd.DataFrame(
        [
            {
                "game_id": "2023_01_AAA_BBB",
                "season": 2023,
                "week": 1,
                "home_team": "AAA",
                "away_team": "BBB",
                "home_score": 24,
                "away_score": 17,
            }
        ]
    )
    stats = pd.DataFrame(
        [
            _season_stats_row("AAA", 2022, epa_offense=0.2, win_pct=0.7),
            _season_stats_row("BBB", 2022, epa_offense=-0.1, win_pct=0.3),
        ]
    )

    feat = build_feature_frame(games, stats)

    assert len(feat) == 1
    row = feat.iloc[0]
    assert row["epa_offense_diff"] == 0.2 - (-0.1)
    assert row["win_pct_diff"] == 0.7 - 0.3
    assert row["home_flag"] == 1
    assert row["home_team_won"] == 1


def test_build_feature_frame_drops_games_missing_prior_stats():
    games = pd.DataFrame(
        [
            {
                "game_id": "2023_01_AAA_BBB",
                "season": 2023,
                "week": 1,
                "home_team": "AAA",
                "away_team": "BBB",
                "home_score": 24,
                "away_score": 17,
            }
        ]
    )
    # Only AAA has 2022 stats; BBB is missing (e.g. first tracked season).
    stats = pd.DataFrame([_season_stats_row("AAA", 2022)])

    feat = build_feature_frame(games, stats)

    assert feat.empty


def test_build_feature_frame_leaves_unplayed_games_unlabeled():
    games = pd.DataFrame(
        [
            {
                "game_id": "2023_01_AAA_BBB",
                "season": 2023,
                "week": 1,
                "home_team": "AAA",
                "away_team": "BBB",
                "home_score": None,
                "away_score": None,
            }
        ]
    )
    stats = pd.DataFrame(
        [_season_stats_row("AAA", 2022), _season_stats_row("BBB", 2022)]
    )

    feat = build_feature_frame(games, stats)

    assert len(feat) == 1
    assert pd.isna(feat.iloc[0]["home_team_won"])
    for col in DIFF_FEATURE_COLUMNS:
        assert col in feat.columns


def test_feature_breakdown_returns_home_minus_away():
    home = {"epa_offense": 0.3, "epa_defense": -0.1, "turnover_margin": 2, "win_pct": 0.6, "yards_per_play": 5.5}
    away = {"epa_offense": 0.1, "epa_defense": 0.05, "turnover_margin": -1, "win_pct": 0.4, "yards_per_play": 5.0}

    breakdown = feature_breakdown(home, away)

    assert breakdown["epa_offense_diff"] == 0.3 - 0.1
    assert breakdown["turnover_margin_diff"] == 2 - (-1)
    assert breakdown["win_pct_diff"] == 0.6 - 0.4


def test_feature_breakdown_handles_missing_stats():
    breakdown = feature_breakdown({"epa_offense": None}, {"epa_offense": 0.1})
    assert breakdown["epa_offense_diff"] is None


def _weekly_row(team_id, season, week, games_played, **overrides):
    row = {
        "team_id": team_id,
        "season": season,
        "week": week,
        "games_played": games_played,
        "epa_offense": 0.0,
        "epa_defense": 0.0,
        "turnover_margin": 0.0,
        "win_pct": 0.5,
        "yards_per_play": 5.0,
        "points_for": 300,
        "points_against": 300,
    }
    row.update(overrides)
    return row


def test_blend_team_stats_at_zero_games_equals_prior():
    prior = {"epa_offense": 0.2, "win_pct": 0.6}
    current = {"epa_offense": -0.5, "win_pct": 0.1}  # should be entirely ignored

    blended = blend_team_stats(prior, current, games_played=0)

    assert blended["epa_offense"] == 0.2
    assert blended["win_pct"] == 0.6


def test_blend_team_stats_at_shrinkage_games_is_even_split():
    prior = {"epa_offense": 0.0}
    current = {"epa_offense": 1.0}

    blended = blend_team_stats(prior, current, games_played=PRIOR_SEASON_SHRINKAGE_GAMES)

    assert blended["epa_offense"] == 0.5


def test_blend_team_stats_approaches_current_as_games_played_grows():
    prior = {"epa_offense": 0.0}
    current = {"epa_offense": 1.0}

    blended = blend_team_stats(prior, current, games_played=100)

    assert blended["epa_offense"] > 0.9


def test_blend_team_stats_missing_prior_is_none():
    blended = blend_team_stats({"epa_offense": None}, {"epa_offense": 1.0}, games_played=10)
    assert blended["epa_offense"] is None


def test_build_feature_frame_blends_in_season_form_into_diffs():
    games = pd.DataFrame(
        [
            {
                "game_id": "2023_08_AAA_BBB",
                "season": 2023,
                "week": 8,
                "home_team": "AAA",
                "away_team": "BBB",
                "home_score": None,
                "away_score": None,
            }
        ]
    )
    # Prior season: dead even.
    stats = pd.DataFrame(
        [_season_stats_row("AAA", 2022, win_pct=0.5), _season_stats_row("BBB", 2022, win_pct=0.5)]
    )
    # This season so far: AAA has been much better, with enough games played
    # that in-season form should dominate the blend.
    weekly = pd.DataFrame(
        [
            _weekly_row("AAA", 2023, 8, games_played=7, win_pct=1.0),
            _weekly_row("BBB", 2023, 8, games_played=7, win_pct=0.0),
        ]
    )

    feat = build_feature_frame(games, stats, weekly)

    assert len(feat) == 1
    # Prior-season-only would give a diff of exactly 0. In-season form
    # should pull it decisively toward AAA.
    assert feat.iloc[0]["win_pct_diff"] > 0.4


def test_build_feature_frame_ignores_weekly_stats_for_a_different_week():
    games = pd.DataFrame(
        [
            {
                "game_id": "2023_08_AAA_BBB",
                "season": 2023,
                "week": 8,
                "home_team": "AAA",
                "away_team": "BBB",
                "home_score": None,
                "away_score": None,
            }
        ]
    )
    stats = pd.DataFrame(
        [_season_stats_row("AAA", 2022, win_pct=0.5), _season_stats_row("BBB", 2022, win_pct=0.5)]
    )
    # Rows exist, but for week 3, not week 8 — shouldn't match this game.
    weekly = pd.DataFrame(
        [
            _weekly_row("AAA", 2023, 3, games_played=2, win_pct=1.0),
            _weekly_row("BBB", 2023, 3, games_played=2, win_pct=0.0),
        ]
    )

    feat = build_feature_frame(games, stats, weekly)

    assert feat.iloc[0]["win_pct_diff"] == 0.0


def test_build_feature_frame_with_explicit_empty_weekly_stats_matches_no_weekly_stats():
    games = pd.DataFrame(
        [
            {
                "game_id": "2023_01_AAA_BBB",
                "season": 2023,
                "week": 1,
                "home_team": "AAA",
                "away_team": "BBB",
                "home_score": 24,
                "away_score": 17,
            }
        ]
    )
    stats = pd.DataFrame(
        [_season_stats_row("AAA", 2022, epa_offense=0.2), _season_stats_row("BBB", 2022, epa_offense=-0.1)]
    )

    without_arg = build_feature_frame(games, stats)
    with_empty_frame = build_feature_frame(games, stats, pd.DataFrame(columns=["team_id", "season", "week", "games_played"]))

    assert without_arg.iloc[0]["epa_offense_diff"] == with_empty_frame.iloc[0]["epa_offense_diff"]
