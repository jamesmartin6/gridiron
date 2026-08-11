import datetime as dt

from ml.season_config import (
    current_nfl_season,
    default_backtest_seasons,
    default_schedule_years,
    default_stats_years,
    default_train_seasons,
)


def test_current_season_during_regular_season():
    assert current_nfl_season(dt.date(2026, 9, 15)) == 2026


def test_current_season_in_january_belongs_to_prior_year():
    assert current_nfl_season(dt.date(2027, 1, 20)) == 2026


def test_current_season_in_february_belongs_to_prior_year():
    assert current_nfl_season(dt.date(2027, 2, 5)) == 2026


def test_current_season_in_march_rolls_over():
    assert current_nfl_season(dt.date(2027, 3, 1)) == 2027


def test_default_ranges_are_consistent_with_current_season():
    today = dt.date(2026, 8, 11)

    assert default_stats_years(today) == list(range(2018, 2026))
    assert default_schedule_years(today) == list(range(2018, 2027))
    assert default_train_seasons(today) == list(range(2020, 2026))
    assert default_backtest_seasons(today) == [2023, 2024, 2025]


def test_default_ranges_shift_correctly_in_january():
    today = dt.date(2027, 1, 20)

    assert default_stats_years(today) == list(range(2018, 2026))
    assert default_schedule_years(today) == list(range(2018, 2027))
    assert default_backtest_seasons(today) == [2023, 2024, 2025]
