from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    phone_or_email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=6, max_length=128)


class SignupResponse(BaseModel):
    message: str


class LoginRequest(BaseModel):
    phone_or_email: str
    password: str


class LoginResponse(BaseModel):
    player_id: UUID
    name: str


class SubmitScoreRequest(BaseModel):
    player_id: UUID
    score: int = Field(..., ge=0)


class PlayerLeaderboardEntry(BaseModel):
    rank: int
    player_id: UUID
    name: str
    score: int
    last_updated: datetime


class LeaderboardResponse(BaseModel):
    total: int
    items: List[PlayerLeaderboardEntry]


class PlayerProfileResponse(BaseModel):
    player_id: UUID
    name: str
    phone_or_email: str
    rank: Optional[int]
    best_score: int
    last_updated: datetime


class ScoreHistoryItem(BaseModel):
    score: int
    created_at: datetime


class PlayerHistoryResponse(BaseModel):
    player_id: UUID
    name: str
    history: List[ScoreHistoryItem]


