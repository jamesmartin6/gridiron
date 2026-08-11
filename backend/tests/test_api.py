from app.models import BacktestResult, Prediction
from tests.factories import add_unplayed_game, seed_multi_season_data


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_list_teams(client, db_session):
    seed_multi_season_data(db_session)

    resp = client.get("/teams")

    assert resp.status_code == 200
    ids = {t["team_id"] for t in resp.json()}
    assert ids == {"AAA", "BBB", "CCC", "DDD"}


def test_team_stats_found(client, db_session):
    seed_multi_season_data(db_session)

    resp = client.get("/teams/AAA/stats", params={"season": 2022})

    assert resp.status_code == 200
    body = resp.json()
    assert body["team_id"] == "AAA"
    assert body["season"] == 2022
    assert body["win_pct"] == 0.75


def test_team_stats_not_found(client, db_session):
    seed_multi_season_data(db_session)

    resp = client.get("/teams/AAA/stats", params={"season": 1999})

    assert resp.status_code == 404


def test_list_games_with_predictions(client, db_session):
    seed_multi_season_data(db_session)
    from app.models import Game

    a_game = db_session.query(Game).filter_by(season=2023).first()
    db_session.add(
        Prediction(game_id=a_game.game_id, model_version="logreg_v1", home_win_prob=0.61)
    )
    db_session.commit()

    resp = client.get("/games", params={"season": 2023, "week": a_game.week})

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) > 0
    match = next(g for g in body if g["game_id"] == a_game.game_id)
    assert match["prediction"]["model_version"] == "logreg_v1"
    assert match["prediction"]["home_win_prob"] == 0.61


def test_list_games_defaults_to_latest_upcoming_week(client, db_session):
    seed_multi_season_data(db_session)
    game_id = add_unplayed_game(db_session, season=2023, week=99, home="AAA", away="BBB")

    resp = client.get("/games")

    assert resp.status_code == 200
    body = resp.json()
    assert any(g["game_id"] == game_id for g in body)


def test_prediction_detail_includes_feature_breakdown(client, db_session):
    seed_multi_season_data(db_session)
    from app.models import Game

    a_game = db_session.query(Game).filter_by(season=2023).first()

    resp = client.get(f"/predictions/{a_game.game_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["game"]["game_id"] == a_game.game_id
    assert body["feature_breakdown"] is not None
    assert "win_pct_diff" in body["feature_breakdown"]


def test_prediction_detail_404_for_unknown_game(client, db_session):
    seed_multi_season_data(db_session)

    resp = client.get("/predictions/does-not-exist")

    assert resp.status_code == 404


def test_backtest_endpoint_lists_results(client, db_session):
    db_session.add(
        BacktestResult(
            model_version="logreg_bt_2023",
            test_season=2023,
            accuracy=0.6,
            log_loss=0.65,
            brier_score=0.22,
            baseline_accuracy=0.5,
            n_games=272,
        )
    )
    db_session.commit()

    resp = client.get("/backtest")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["model_version"] == "logreg_bt_2023"
    assert body[0]["accuracy"] == 0.6


def test_predict_endpoint_writes_predictions(client, db_session, tmp_path, monkeypatch):
    from app.config import get_settings

    seed_multi_season_data(db_session)
    game_id = add_unplayed_game(db_session, season=2023, week=99, home="AAA", away="DDD")

    from ml import train as train_mod
    from tests.factories import SEASONS_WITH_GAMES

    train_mod.train(
        seasons=SEASONS_WITH_GAMES, model_type="logreg", version="api_test_v1", model_dir=str(tmp_path)
    )

    get_settings.cache_clear()
    monkeypatch.setenv("MODEL_DIR", str(tmp_path))
    get_settings.cache_clear()

    resp = client.post(
        "/predict", params={"season": 2023, "week": 99, "model_version": "api_test_v1"}
    )

    get_settings.cache_clear()

    assert resp.status_code == 200
    assert resp.json()["n_predictions"] == 1
    pred = db_session.get(Prediction, {"game_id": game_id, "model_version": "api_test_v1"})
    assert pred is not None
