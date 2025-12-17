"""Small helper script to populate some sample players and scores.

Run locally (with Postgres and Redis running):

    python sample_data.py
"""

from datetime import datetime, timedelta
import random

from backend.database import db_session, Base, engine
from backend.models import PlayerInfo, PlayerLeaderboard, ScoreHistory
from backend.main import hash_password
from backend.redis_client import update_leaderboard


def create_schema() -> None:
    Base.metadata.create_all(bind=engine)


def create_sample_players() -> None:
    names = ["Alice", "Bob", "Charlie", "Daisy", "Eve", "Frank", "Grace", "Heidi"]

    with db_session() as db:
        for i, name in enumerate(names):
            contact = f"user{i+1}@example.com"
            player = PlayerInfo(
                name=name,
                phone_or_email=contact,
                password_hash=hash_password("password"),
            )
            db.add(player)
            db.flush()

            best_score = 0
            best_ts = datetime.utcnow()

            for j in range(5):
                score = random.randint(10, 200)
                ts = datetime.utcnow() - timedelta(minutes=(5 - j))
                history = ScoreHistory(player_id=player.player_id, score=score, created_at=ts)
                db.add(history)
                if score > best_score:
                    best_score = score
                    best_ts = ts

            leaderboard = PlayerLeaderboard(
                player_id=player.player_id,
                best_score=best_score,
                last_updated=best_ts,
            )
            db.add(leaderboard)

        db.commit()

    # Mirror to Redis
    with db_session() as db:
        players = db.query(PlayerLeaderboard).all()
        for pl in players:
            update_leaderboard(
                player_id=pl.player_id,
                best_score=pl.best_score,
                achieved_at=pl.last_updated.timestamp(),
            )


if __name__ == "__main__":
    create_schema()
    create_sample_players()
    print("Sample data created.")


