## Video Game Leaderboard System

A simple but scalable full-stack leaderboard system for an online game using **FastAPI**, **PostgreSQL**, **Redis**, and a vanilla **HTML/CSS/JS** frontend.
#### Demo video: [Click here to watch](https://drive.google.com/file/d/1kCrFlZyTgn-7318ZGwWrG_OfvV5vXaNB/view)
### Features

- **Player signup & login**
- **Simple clicker game** in the browser
- **Score submission** to backend
- **Top-N global leaderboard** (Top 10 on UI)
- **Player profile**: rank, best score, last updated
- **Score history**: last N scores per player

### Architecture

- **PostgreSQL**: source of truth for players and scores.
- **Redis ZSET** `global:leaderboard`:
  - `member = player_id`
  - `score = encoded(best_score, achieved_at)` to support tie-breaking
- **Redis HASH** `player:meta:{player_id}`:
  - `best_score`
  - `last_updated_epoch`
- **FastAPI** for REST APIs.

The Redis logic corresponds to the idea of keeping:
- A **map** from player to their best score/metadata (Postgres + Redis HASH).
- A **sorted set** as an ordered view of players by score and timestamp (Redis ZSET),
  similar to my `set<struct, Compare>` concept.

### Prerequisites

- Docker and Docker Compose

### Running with Docker Compose

From the project root (`Leaderboard`):

```bash
docker compose up --build
```

Services:

- `backend`: FastAPI app on `http://localhost:8000`
- `db`: PostgreSQL on `localhost:5432`
- `redis`: Redis on `localhost:6379`

Once everything is up, you can optionally create sample data and run tests – see the next sections.


### Sample Data (`sample_data.py`)

`sample_data.py` creates a few demo players with random scores, fills **Postgres** tables, and mirrors the best scores into **Redis**.

- **With Docker Compose (recommended)**:

  - Make sure containers are running:

  ```bash
  docker compose up --build
  ```

  - In another terminal, from the project root:

  ```bash
  docker compose exec backend python sample_data.py
  ```

  This will:

  - Create tables if they don't exist.
  - Insert sample players and their score histories.
  - Compute each player’s `best_score` + `last_updated` and push to Redis ZSET/HASH.

- **Without Docker (local Python)**:

  - Ensure Postgres + Redis are running locally and `backend/config.py` points to them.
  - Then run:

  ```bash
  python sample_data.py
  ```

After this, opening the frontend will show a pre-filled leaderboard and players you can log in as (`user1@example.com` … etc., with password `password`). 

### Running Backend Locally (without Docker)

1. Create and activate a virtualenv (optional but recommended).
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Ensure Postgres and Redis are running locally:

- Postgres:
  - user: `leaderboard`
  - password: `leaderboard`
  - db: `leaderboard`
  - port: `5432`
- Redis:
  - host: `localhost`
  - port: `6379`

4. Start FastAPI:

```bash
uvicorn backend.main:app --reload --port 8000
```

### Running Tests

The project includes **pytest** tests under `tests/` which exercise all main APIs end-to-end (FastAPI + Postgres + Redis).

- **With Docker Compose**:

```bash
docker compose up --build      # if not already running
docker compose exec backend pytest
```

- **Without Docker (local)**:

```bash
pip install -r requirements.txt
pytest
```

#### What the tests cover

- **`test_signup_and_login_flow`**
  - Successful signup.
  - Duplicate signup rejected with `400` (same `phone_or_email`).
  - Successful login with correct credentials.
  - Login failure (`401`) with wrong password.

- **`test_score_submission_and_leaderboard`**
  - Signup + login to get `player_id`.
  - Submit scores `[10, 50, 30]` via `/submit-score`.
  - `/player/{id}` returns:
    - `best_score == 50`
    - `rank == 1` (from Redis).
  - `/leaderboard/top?n=10` returns one row for that player with score `50`.
  - `/player/{id}/history?limit=10` returns 3 history entries (all submitted scores).

- **`test_submit_score_invalid_player_and_history_limit`**
  - `/submit-score` with a random/non-existent `player_id` returns `404`.
  - For a real player, submits 20 scores, then:
    - `/player/{id}/history?limit=5` returns exactly 5 most recent scores.

- **`test_leaderboard_multiple_players_ordering`**
  - Creates two players: Alice and Bob.
  - Alice best score: `100`, Bob best score: `50`.
  - `/leaderboard/top?n=10` returns 2 rows:
    - Row 1: Alice, score `100`.
    - Row 2: Bob, score `50`.
  - Confirms that the **higher best score** ranks above, consistent with the leaderboard logic.

### Frontend (Game UI)

The frontend is plain static files under `frontend/`.

You can open it directly:

- On Windows: open `frontend/index.html` in my browser
- Or serve it with a simple HTTP server, e.g.:

```bash
cd frontend
python -m http.server 5500
```

Then open `http://localhost:5500/index.html`.  
The JS expects the backend at `http://localhost:8000` (configure via `API_BASE` in `script.js`).

### API Overview

#### `POST /signup`

- **Input** (JSON):

```json
{
  "name": "Alice",
  "phone_or_email": "alice@example.com",
  "password": "secret123"
}
```

- **Output**:

```json
{
  "message": "Signup successful. Please log in."
}
```

> Note: `player_id` is created but not returned here. The frontend obtains it later via `/login`.

#### `POST /login`

- **Input**:

```json
{
  "phone_or_email": "alice@example.com",
  "password": "secret123"
}
```

- **Output**:

```json
{
  "player_id": "UUID",
  "name": "Alice"
}
```

The frontend stores `player_id` in `localStorage` and uses it for subsequent score submissions and profile queries.

#### `POST /submit-score`

- **Input**:

```json
{
  "player_id": "UUID",
  "score": 150
}
```

- **Behavior**:
  - Inserts into `score_history`.
  - Updates `playerleaderboard.best_score` and `last_updated` **iff** this is a new best.
  - Updates Redis ZSET `global:leaderboard` and hash `player:meta:{player_id}`.

- **Output**:

```json
{ "message": "Score submitted" }
```

#### `GET /leaderboard/top?n=10`

- **Output**:

```json
{
  "total": 3,
  "items": [
    {
      "rank": 1,
      "player_id": "UUID",
      "name": "Alice",
      "score": 200,
      "last_updated": "2025-12-17T12:34:56.789Z"
    }
  ]
}
```

Leaderboards are read primarily from Redis:

- `ZREVRANGE global:leaderboard 0 N-1 WITHSCORES`  
  gives the top N player IDs and their encoded scores.

The backend then fetches player details (name, timestamps) from Postgres and returns them.

#### `GET /player/{player_id}`

- **Output**:

```json
{
  "player_id": "UUID",
  "name": "Alice",
  "phone_or_email": "alice@example.com",
  "rank": 1,
  "best_score": 200,
  "last_updated": "2025-12-17T12:34:56.789Z"
}
```

Rank is derived from Redis via:

- `ZREVRANK global:leaderboard {player_id}`

#### `GET /player/{player_id}/history?limit=10`

- **Output**:

```json
{
  "player_id": "UUID",
  "name": "Alice",
  "history": [
    { "score": 120, "created_at": "..." },
    { "score": 200, "created_at": "..." }
  ]
}
```

### Tie-Breaker & Complexity Notes

- **Tie-breaker rule**: if two players have the same `best_score`, the player who achieved it **earlier** ranks higher.
- In Redis we encode both the score and timestamp into a single float:
  - `encoded = best_score * 1e9 - achieved_at_ms`
  - Higher `best_score` ⇒ larger `encoded`.
  - For equal score, smaller `achieved_at_ms` (earlier) ⇒ larger `encoded`.

#### Mapping from my C++ logic to Python + Redis

Original C++ idea (simplified):

```cpp
struct Player { int id; int score; long long lastUpdated; };
struct Compare {
  bool operator()(const Player& a, const Player& b) const {
    if (a.score != b.score) return a.score > b.score;          // higher score first
    if (a.lastUpdated != b.lastUpdated) return a.lastUpdated < b.lastUpdated; // earlier time first
    return a.id < b.id;
  }
};
std::set<Player, Compare> st;                    // ordered leaderboard
std::unordered_map<int, std::set<Player>::iterator> mp;  // id -> iterator (fast updates)
```

**Python/Redis equivalent in this project:**

- **`unordered_map<int, iterator>` → persistent + cached meta:**
  - Postgres table `playerleaderboard`:
    - `player_id`, `best_score`, `last_updated`.
  - Redis HASH `player:meta:{player_id}`:
    - `best_score`, `last_updated_epoch`.

- **`set<Player, Compare>` → Redis sorted set:**
  - Redis ZSET `global:leaderboard`:
    - `member = player_id`.
    - `score = encoded(best_score, lastUpdated)` using:

    ```python
    encoded = best_score * 1_000_000_000.0 - achieved_at_ms
    ```

    This keeps ordering identical to my `Compare` functor:

    - Higher `best_score` ⇒ larger `encoded` ⇒ comes first (`ZREVRANGE`).
    - For equal `best_score`, smaller `achieved_at_ms` (earlier) ⇒ larger `encoded` ⇒ earlier rank.

- **Update flow (C++ erase+insert) → DB + Redis update:**

  - On score submission:
    - Append to `score_history` in Postgres.
    - Update row in `playerleaderboard` if it’s a new best (and set `last_updated` accordingly).
    - Call `update_leaderboard(player_id, best_score, achieved_at)` which does:
      - `ZADD global:leaderboard {player_id: encoded_score}`.
      - `HSET player:meta:{player_id} best_score last_updated_epoch`.

So the combination of **Postgres tables + Redis ZSET/HASH** is the production-grade version of my in-memory `map<int, struct>` + `set<struct, Compare>` pattern, with the same ranking and tie-break semantics but designed to scale across many players and processes.

**Time complexity**:

- Score update:
  - Postgres write: O(1) (amortized)
  - Redis `ZADD`: O(log N)
- Top N:
  - Redis `ZREVRANGE`: O(log N + N)
- Rank lookup:
  - Redis `ZREVRANK`: O(log N)

This keeps reads **fast (<15ms)** for large N and frequent updates, with Redis as the hot path and Postgres as the durable store.




