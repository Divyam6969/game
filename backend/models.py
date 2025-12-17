import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    BigInteger,
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .database import Base


class PlayerInfo(Base):
    """Core player identity and contact info."""

    __tablename__ = "playerinfo"

    player_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name = Column(String, nullable=False)
    phone_or_email = Column(String, nullable=False, unique=True)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    leaderboard = relationship(
        "PlayerLeaderboard",
        uselist=False,
        back_populates="player",
        cascade="all, delete-orphan",
    )
    scores = relationship(
        "ScoreHistory",
        back_populates="player",
        cascade="all, delete-orphan",
    )


class PlayerLeaderboard(Base):
    """Aggregated leaderboard state per player.

    Stores only the best score and the timestamp when that best score
    was achieved. This is what we mirror into Redis for fast reads.
    """

    __tablename__ = "playerleaderboard"

    player_id = Column(
        UUID(as_uuid=True),
        ForeignKey("playerinfo.player_id", ondelete="CASCADE"),
        primary_key=True,
    )
    best_score = Column(Integer, nullable=False, default=0)
    last_updated = Column(DateTime, nullable=False, default=datetime.utcnow)

    player = relationship("PlayerInfo", back_populates="leaderboard")

    __table_args__ = (
        Index("idx_playerleaderboard_best_score_desc", "best_score", "last_updated"),
    )


class ScoreHistory(Base):
    """Immutable history of all score submissions."""

    __tablename__ = "score_history"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    player_id = Column(
        UUID(as_uuid=True),
        ForeignKey("playerinfo.player_id", ondelete="CASCADE"),
        nullable=False,
    )
    score = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    player = relationship("PlayerInfo", back_populates="scores")

    __table_args__ = (
        Index(
            "idx_score_history_player_created_desc",
            "player_id",
            "created_at",
        ),
    )


