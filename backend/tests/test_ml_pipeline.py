from pathlib import Path

from app.models import BacktestResult, Prediction
from ml import backtest as backtest_mod
from ml import predict as predict_mod
from ml import train as train_mod
from tests.factories import SEASONS_WITH_GAMES, add_unplayed_game, seed_multi_season_data


def test_train_produces_a_model_that_outputs_probabilities(db_session, tmp_path):
    seed_multi_season_data(db_session)

    meta = train_mod.train(
        seasons=SEASONS_WITH_GAMES,
        model_type="logreg",
        version="test_v1",
        model_dir=str(tmp_path),
    )

    assert meta["n_training_rows"] > 0
    assert (tmp_path / "model_test_v1.pkl").exists()

    model = predict_mod.load_model("test_v1", str(tmp_path))
    import pandas as pd

    probs = model.predict_proba(pd.DataFrame([[0.1, -0.1, 1, 0.1, 0.5, 1]], columns=train_mod.FEATURE_COLUMNS))
    assert probs.shape == (1, 2)
    assert 0.0 <= probs[0, 1] <= 1.0


def test_backtest_beats_baseline_on_separable_synthetic_data(db_session, tmp_path):
    seed_multi_season_data(db_session)

    results = backtest_mod.run_backtest(
        seasons=[2022, 2023], model_type="logreg", model_dir=str(tmp_path)
    )

    assert len(results) == 2
    for r in results:
        assert set(r) >= {
            "test_season",
            "accuracy",
            "log_loss",
            "brier_score",
            "baseline_accuracy",
            "n_games",
            "model_version",
        }
        # Strength perfectly determines the outcome in the synthetic data,
        # so a model with the right features should score well above a
        # coin-flip baseline (and above the always-home baseline, which is
        # exactly 0.5 by construction of the fixture).
        assert r["baseline_accuracy"] == 0.5
        assert r["accuracy"] >= r["baseline_accuracy"]
        assert 0.0 <= r["accuracy"] <= 1.0
        assert r["log_loss"] > 0

    rows = db_session.query(BacktestResult).all()
    assert len(rows) == 2
    versions = {row.model_version for row in rows}
    assert versions == {"logreg_bt_2022", "logreg_bt_2023"}


def test_backtest_rerun_overwrites_rather_than_duplicates(db_session, tmp_path):
    seed_multi_season_data(db_session)

    backtest_mod.run_backtest(seasons=[2023], model_type="logreg", model_dir=str(tmp_path))
    backtest_mod.run_backtest(seasons=[2023], model_type="logreg", model_dir=str(tmp_path))

    rows = db_session.query(BacktestResult).filter_by(test_season=2023).all()
    assert len(rows) == 1


def test_predict_writes_predictions_for_upcoming_games(db_session, tmp_path):
    seed_multi_season_data(db_session)
    game_id = add_unplayed_game(db_session, season=2023, week=99, home="AAA", away="DDD")

    train_mod.train(
        seasons=SEASONS_WITH_GAMES, model_type="logreg", version="test_v1", model_dir=str(tmp_path)
    )
    n = predict_mod.run_predict(version="test_v1", model_dir=str(tmp_path), season=2023, week=99)

    assert n == 1
    pred = db_session.get(Prediction, {"game_id": game_id, "model_version": "test_v1"})
    assert pred is not None
    # AAA is the strongest team, DDD the weakest -> should be favored.
    assert pred.home_win_prob > 0.5
