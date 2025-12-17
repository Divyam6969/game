from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from .config import get_settings
from .database import Base, engine, get_db
from .models import PlayerInfo, PlayerLeaderboard, ScoreHistory
from .redis_client import (
    update_leaderboard,
    get_top_n_from_redis,
    get_rank_from_redis,
)
from . import schemas

settings = get_settings()

# Use pbkdf2_sha256 instead of bcrypt to avoid environment-specific bcrypt
# backend issues (like the 72-byte password limit and wrap-bug checks).
# For a demo project this is perfectly fine and simpler to run everywhere.
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

app = FastAPI(title=settings.PROJECT_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    """Create tables on startup for demo purposes.

    In production you would use Alembic migrations instead.
    """
    Base.metadata.create_all(bind=engine)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


@app.post("/signup", response_model=schemas.SignupResponse)
def signup(payload: schemas.SignupRequest, db: Session = Depends(get_db)):
    """Create a new player.

    Note: For simplicity, this endpoint does not return the player_id.
    The frontend should use /login to obtain it after signup.
    """
    existing = (
        db.query(PlayerInfo)
        .filter(PlayerInfo.phone_or_email == payload.phone_or_email)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    player = PlayerInfo(
        name=payload.name,
        phone_or_email=payload.phone_or_email,
        password_hash=hash_password(payload.password),
    )
    db.add(player)
    db.flush()  # ensure player_id is generated

    # Initialize leaderboard row with score 0
    leaderboard = PlayerLeaderboard(
        player_id=player.player_id,
        best_score=0,
        last_updated=datetime.utcnow(),
    )
    db.add(leaderboard)

    db.commit()

    return schemas.SignupResponse(message="Signup successful. Please log in.")


@app.post("/login", response_model=schemas.LoginResponse)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    """Simple login returning player_id so frontend can associate scores."""
    player = (
        db.query(PlayerInfo)
        .filter(PlayerInfo.phone_or_email == payload.phone_or_email)
        .first()
    )
    if not player or not verify_password(payload.password, player.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return schemas.LoginResponse(player_id=player.player_id, name=player.name)


@app.post("/submit-score")
def submit_score(payload: schemas.SubmitScoreRequest, db: Session = Depends(get_db)):
    """Submit a new score for a player.

    Operations:
    - Insert into score_history (append-only).
    - Update playerleaderboard.best_score and last_updated if this is a new best.
    - Update Redis leaderboard mirror.
    """
    player = db.query(PlayerInfo).filter(PlayerInfo.player_id == payload.player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    now = datetime.utcnow()

    # 1. Insert into score_history
    history = ScoreHistory(
        player_id=payload.player_id,
        score=payload.score,
        created_at=now,
    )
    db.add(history)

    # 2. Update leaderboard row if this is a better score
    leaderboard = (
        db.query(PlayerLeaderboard)
        .filter(PlayerLeaderboard.player_id == payload.player_id)
        .with_for_update()
        .first()
    )
    if leaderboard is None:
        leaderboard = PlayerLeaderboard(
            player_id=payload.player_id,
            best_score=payload.score,
            last_updated=now,
        )
        db.add(leaderboard)
    else:
        # Tie-breaker: if scores are equal, earlier timestamp wins.
        # Here we update last_updated only if score is strictly higher.
        if payload.score > leaderboard.best_score:
            leaderboard.best_score = payload.score
            leaderboard.last_updated = now

    db.commit()

    # 3. Mirror into Redis (using best_score + last_updated timestamp).
    update_leaderboard(
        player_id=leaderboard.player_id,
        best_score=leaderboard.best_score,
        achieved_at=leaderboard.last_updated.timestamp(),
    )

    return {"message": "Score submitted"}


@app.get("/leaderboard/top", response_model=schemas.LeaderboardResponse)
def get_top_leaderboard(
    n: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Return Top-N players using Redis for ranking + Postgres for details."""
    redis_entries = get_top_n_from_redis(n)
    player_ids: List[UUID] = [UUID(pid) for pid, _ in redis_entries]

    if not player_ids:
        return schemas.LeaderboardResponse(total=0, items=[])

    players = (
        db.query(PlayerInfo, PlayerLeaderboard)
        .join(PlayerLeaderboard, PlayerInfo.player_id == PlayerLeaderboard.player_id)
        .filter(PlayerInfo.player_id.in_(player_ids))
        .all()
    )
    info_map = {
        str(player.player_id): (player, leaderboard) for player, leaderboard in players
    }

    items: List[schemas.PlayerLeaderboardEntry] = []
    for idx, (pid_str, _) in enumerate(redis_entries):
        info = info_map.get(pid_str)
        if not info:
            # In case of slight inconsistencies, skip missing players.
            continue
        player, leaderboard = info
        items.append(
            schemas.PlayerLeaderboardEntry(
                rank=idx + 1,
                player_id=player.player_id,
                name=player.name,
                score=leaderboard.best_score,
                last_updated=leaderboard.last_updated,
            )
        )

    return schemas.LeaderboardResponse(total=len(items), items=items)


@app.get("/player/{player_id}", response_model=schemas.PlayerProfileResponse)
def get_player_profile(player_id: UUID, db: Session = Depends(get_db)):
    """Return a player profile including current rank and best score."""
    result = (
        db.query(PlayerInfo, PlayerLeaderboard)
        .join(PlayerLeaderboard, PlayerInfo.player_id == PlayerLeaderboard.player_id)
        .filter(PlayerInfo.player_id == player_id)
        .first()
    )
    if not result:
        raise HTTPException(status_code=404, detail="Player not found")

    player_info, leaderboard = result
    rank = get_rank_from_redis(player_id)

    return schemas.PlayerProfileResponse(
        player_id=player_info.player_id,
        name=player_info.name,
        phone_or_email=player_info.phone_or_email,
        rank=rank,
        best_score=leaderboard.best_score,
        last_updated=leaderboard.last_updated,
    )


@app.get(
    "/player/{player_id}/history",
    response_model=schemas.PlayerHistoryResponse,
)
def get_player_history(
    player_id: UUID,
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Return the last N scores for a specific player."""
    player = db.query(PlayerInfo).filter(PlayerInfo.player_id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    scores = (
        db.query(ScoreHistory)
        .filter(ScoreHistory.player_id == player_id)
        .order_by(ScoreHistory.created_at.desc())
        .limit(limit)
        .all()
    )

    history = [
        schemas.ScoreHistoryItem(score=s.score, created_at=s.created_at)
        for s in scores
    ]

    return schemas.PlayerHistoryResponse(
        player_id=player.player_id,
        name=player.name,
        history=history,
    )


