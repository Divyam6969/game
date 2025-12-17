import uuid

from fastapi.testclient import TestClient

from backend.main import app
from backend.database import db_session
from backend.models import PlayerInfo, PlayerLeaderboard, ScoreHistory
from backend.redis_client import get_redis_client


client = TestClient(app)


def reset_state():
    """Clear database tables and Redis between tests."""
    with db_session() as db:
        db.query(ScoreHistory).delete()
        db.query(PlayerLeaderboard).delete()
        db.query(PlayerInfo).delete()
    r = get_redis_client()
    r.flushdb()


def test_signup_and_login_flow():
    reset_state()

    # 1) Signup
    signup_payload = {
        "name": "TestUser",
        "phone_or_email": "testuser",
        "password": "password123",
    }
    resp = client.post("/signup", json=signup_payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "Signup successful" in data["message"]

    # 2) Duplicate signup should fail
    resp = client.post("/signup", json=signup_payload)
    assert resp.status_code == 400

    # 3) Login
    login_payload = {
        "phone_or_email": "testuser",
        "password": "password123",
    }
    resp = client.post("/login", json=login_payload)
    assert resp.status_code == 200
    login_data = resp.json()
    assert "player_id" in login_data
    assert login_data["name"] == "TestUser"

    # 4) Login with wrong password should fail
    bad_login_payload = {
        "phone_or_email": "testuser",
        "password": "wrongpassword",
    }
    resp = client.post("/login", json=bad_login_payload)
    assert resp.status_code == 401


def test_score_submission_and_leaderboard():
    reset_state()

    # Create a player
    signup_payload = {
        "name": "Player1",
        "phone_or_email": "player1",
        "password": "password123",
    }
    assert client.post("/signup", json=signup_payload).status_code == 200

    login_payload = {
        "phone_or_email": "player1",
        "password": "password123",
    }
    resp = client.post("/login", json=login_payload)
    assert resp.status_code == 200
    player = resp.json()
    player_id = player["player_id"]

    # Submit multiple scores
    for score in [10, 50, 30]:
        resp = client.post(
            "/submit-score",
            json={"player_id": player_id, "score": score},
        )
        assert resp.status_code == 200

    # Check profile
    resp = client.get(f"/player/{player_id}")
    assert resp.status_code == 200
    profile = resp.json()
    assert profile["best_score"] == 50
    assert profile["rank"] == 1

    # Check leaderboard
    resp = client.get("/leaderboard/top?n=10")
    assert resp.status_code == 200
    leaderboard = resp.json()
    assert leaderboard["total"] == 1
    assert leaderboard["items"][0]["player_id"] == player_id
    assert leaderboard["items"][0]["score"] == 50

    # Check history (should have 3 entries)
    resp = client.get(f"/player/{player_id}/history?limit=10")
    assert resp.status_code == 200
    history = resp.json()
    assert len(history["history"]) == 3


def test_submit_score_invalid_player_and_history_limit():
    reset_state()

    # Submit score with unknown player_id should 404
    random_id = str(uuid.uuid4())
    resp = client.post("/submit-score", json={"player_id": random_id, "score": 10})
    assert resp.status_code == 404

    # Create a real player and submit many scores
    signup_payload = {
        "name": "HistoryUser",
        "phone_or_email": "historyuser",
        "password": "password123",
    }
    client.post("/signup", json=signup_payload)
    login_payload = {
        "phone_or_email": "historyuser",
        "password": "password123",
    }
    resp = client.post("/login", json=login_payload)
    player_id = resp.json()["player_id"]

    for score in range(20):
        client.post("/submit-score", json={"player_id": player_id, "score": score})

    # Limit=5 should only return 5 recent scores
    resp = client.get(f"/player/{player_id}/history?limit=5")
    assert resp.status_code == 200
    history = resp.json()
    assert len(history["history"]) == 5


def test_leaderboard_multiple_players_ordering():
    reset_state()

    # Create two players
    for name, contact in [("Alice", "alice"), ("Bob", "bob")]:
        client.post(
            "/signup",
            json={
                "name": name,
                "phone_or_email": contact,
                "password": "password123",
            },
        )

    # Login and capture IDs
    resp_a = client.post(
        "/login", json={"phone_or_email": "alice", "password": "password123"}
    )
    resp_b = client.post(
        "/login", json={"phone_or_email": "bob", "password": "password123"}
    )
    a_id = resp_a.json()["player_id"]
    b_id = resp_b.json()["player_id"]

    # Alice: best score 100, Bob: best score 50
    client.post("/submit-score", json={"player_id": a_id, "score": 100})
    client.post("/submit-score", json={"player_id": b_id, "score": 50})

    resp = client.get("/leaderboard/top?n=10")
    assert resp.status_code == 200
    leaderboard = resp.json()["items"]
    assert len(leaderboard) == 2
    # Alice should be rank 1
    assert leaderboard[0]["player_id"] == a_id
    assert leaderboard[0]["score"] == 100


