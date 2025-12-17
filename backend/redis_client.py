import time
from typing import List, Tuple
from uuid import UUID

import redis

from .config import get_settings

settings = get_settings()


def get_redis_client() -> redis.Redis:
    """Create a Redis client instance.

    In production you might want a singleton; here we create a cheap client
    per usage. redis-py pools connections internally.
    """
    return redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        decode_responses=True,
    )


GLOBAL_LEADERBOARD_KEY = "global:leaderboard"
PLAYER_META_KEY_PREFIX = "player:meta:"


def _encode_score_with_tiebreaker(best_score: int, achieved_ts_ms: int) -> float:
    """Encode score and timestamp into a single float for Redis ZSET.

    Higher score must rank higher. For equal scores, earlier timestamp wins.

    We use: encoded = best_score * 1e9 - achieved_ts_ms
    - Larger best_score gives larger encoded value.
    - For same best_score, smaller achieved_ts_ms (earlier) gives larger encoded.

    This keeps ordering consistent with our tie-breaker rule while staying
    within 64-bit float precision for typical score ranges.
    """
    return float(best_score) * 1_000_000_000.0 - float(achieved_ts_ms)


def update_leaderboard(player_id: UUID, best_score: int, achieved_at: float) -> None:
    """Update Redis ZSET + player hash for a player.

    Time complexity:
    - ZADD: O(log N)
    - HSET: O(1)
    Overall per update ~O(log N), scales to large leaderboards.
    """
    r = get_redis_client()
    ts_ms = int(achieved_at * 1000)
    encoded_score = _encode_score_with_tiebreaker(best_score, ts_ms)

    pipe = r.pipeline(transaction=True)
    pipe.zadd(GLOBAL_LEADERBOARD_KEY, {str(player_id): encoded_score})
    meta_key = f"{PLAYER_META_KEY_PREFIX}{player_id}"
    pipe.hset(
        meta_key,
        mapping={
            "best_score": best_score,
            "last_updated_epoch": ts_ms,
        },
    )
    pipe.execute()


def get_top_n_from_redis(n: int) -> List[Tuple[str, float]]:
    """Return top N players (player_id, encoded_score) from Redis.

    Uses ZREVRANGE (O(log N + M) where M = N).
    """
    r = get_redis_client()
    return r.zrevrange(GLOBAL_LEADERBOARD_KEY, 0, n - 1, withscores=True)


def get_rank_from_redis(player_id: UUID) -> int | None:
    """Return 1-based rank for a player from Redis, or None if not present.

    Uses ZREVRANK: O(log N)
    """
    r = get_redis_client()
    rank = r.zrevrank(GLOBAL_LEADERBOARD_KEY, str(player_id))
    if rank is None:
        return None
    # Redis ranks are 0-based, convert to 1-based for user-facing APIs.
    return rank + 1


