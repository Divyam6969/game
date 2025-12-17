// Simple config: adjust if backend is hosted elsewhere
const API_BASE = "http://localhost:8000";

let currentPlayerId = null;
let currentPlayerName = null;

let gameTimer = null;
let timeLeft = 0;
let currentScore = 0;
let leaderboardCount = 10;

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function showMessage(text, isError = false) {
  const el = document.getElementById("game-message");
  if (!el) return;
  el.textContent = text;
  el.style.color = isError ? "#f87171" : "#9ca3af";
}

async function apiRequest(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
    },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Request failed: ${res.status}`);
  }
  // Some endpoints return plain JSON objects, others structured ones
  const contentType = res.headers.get("Content-Type") || "";
  if (contentType.includes("application/json")) {
    return res.json();
  }
  return null;
}

async function loadPlayerFromStorage() {
  const storedId = localStorage.getItem("player_id");
  const storedName = localStorage.getItem("player_name");
  if (storedId && storedName) {
    // Verify player still exists in backend before auto-logging in
    try {
      const data = await apiRequest(`/player/${storedId}`);
      // If player exists, set as logged in
      currentPlayerId = storedId;
      currentPlayerName = storedName;
      setText("current-player", `Logged in as ${currentPlayerName}`);
      const logoutBtn = document.getElementById("logout-btn");
      if (logoutBtn) logoutBtn.style.display = "inline-block";
      refreshPlayerViews();
    } catch (err) {
      // Player doesn't exist or backend unavailable - clear localStorage
      console.log("Stored player not found or backend unavailable, clearing login:", err);
      localStorage.removeItem("player_id");
      localStorage.removeItem("player_name");
      currentPlayerId = null;
      currentPlayerName = null;
      setText("current-player", "");
      const logoutBtn = document.getElementById("logout-btn");
      if (logoutBtn) logoutBtn.style.display = "none";
    }
  }
}

function savePlayerToStorage(playerId, name) {
  localStorage.setItem("player_id", playerId);
  localStorage.setItem("player_name", name);
}

document.getElementById("signup-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const name = document.getElementById("signup-name").value.trim();
  const contact = document.getElementById("signup-contact").value.trim();
  const password = document.getElementById("signup-password").value;
  try {
    await apiRequest("/signup", {
      method: "POST",
      body: JSON.stringify({
        name,
        phone_or_email: contact,
        password,
      }),
    });
    alert("Signup successful! Please log in.");
    e.target.reset();
  } catch (err) {
    alert(err.message);
  }
});

document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const contact = document.getElementById("login-contact").value.trim();
  const password = document.getElementById("login-password").value;
  try {
    const resp = await apiRequest("/login", {
      method: "POST",
      body: JSON.stringify({
        phone_or_email: contact,
        password,
      }),
    });
    currentPlayerId = resp.player_id;
    currentPlayerName = resp.name;
    savePlayerToStorage(currentPlayerId, currentPlayerName);
    setText("current-player", `Logged in as ${currentPlayerName}`);
    const logoutBtn = document.getElementById("logout-btn");
    if (logoutBtn) logoutBtn.style.display = "inline-block";
    refreshPlayerViews();
    alert("Login successful!");
  } catch (err) {
    alert(err.message);
  }
});

// Game logic
document.getElementById("start-game").addEventListener("click", () => {
  if (!currentPlayerId) {
    alert("Please log in first.");
    return;
  }
  if (gameTimer) {
    clearInterval(gameTimer);
  }
  timeLeft = 10;
  currentScore = 0;
  setText("time-left", timeLeft.toString());
  setText("current-score", currentScore.toString());
  showMessage("Game started! Click as fast as you can.");
  document.getElementById("click-btn").disabled = false;
  document.getElementById("submit-score").disabled = true;

  gameTimer = setInterval(() => {
    timeLeft -= 1;
    setText("time-left", timeLeft.toString());
    if (timeLeft <= 0) {
      clearInterval(gameTimer);
      gameTimer = null;
      document.getElementById("click-btn").disabled = true;
      document.getElementById("submit-score").disabled = false;
      showMessage(`Time up! Your score: ${currentScore}`);
    }
  }, 1000);
});

document.getElementById("click-btn").addEventListener("click", () => {
  if (timeLeft > 0) {
    currentScore += 1;
    setText("current-score", currentScore.toString());
  }
});

document.getElementById("submit-score").addEventListener("click", async () => {
  if (!currentPlayerId) {
    alert("Please log in first.");
    return;
  }
  try {
    await apiRequest("/submit-score", {
      method: "POST",
      body: JSON.stringify({
        player_id: currentPlayerId,
        score: currentScore,
      }),
    });
    showMessage("Score submitted successfully!");
    document.getElementById("submit-score").disabled = true;
    refreshPlayerViews();
  } catch (err) {
    showMessage(err.message, true);
  }
});

// Logout: purely client-side (since we're not using tokens here)
document.getElementById("logout-btn").addEventListener("click", () => {
  currentPlayerId = null;
  currentPlayerName = null;
  localStorage.removeItem("player_id");
  localStorage.removeItem("player_name");
  setText("current-player", "");
  const logoutBtn = document.getElementById("logout-btn");
  if (logoutBtn) logoutBtn.style.display = "none";

  // Reset game state
  if (gameTimer) {
    clearInterval(gameTimer);
    gameTimer = null;
  }
  timeLeft = 0;
  currentScore = 0;
  setText("time-left", "0");
  setText("current-score", "0");
  document.getElementById("click-btn").disabled = true;
  document.getElementById("submit-score").disabled = true;
  showMessage("You have logged out.");

  // Clear profile & history view
  setText("profile-rank", "-");
  setText("profile-best-score", "-");
  setText("profile-last-updated", "-");
  const list = document.getElementById("history-list");
  if (list) list.innerHTML = "";

});

async function loadLeaderboard() {
  try {
    const data = await apiRequest(`/leaderboard/top?n=${leaderboardCount}`);
    const tbody = document
      .getElementById("leaderboard-table")
      .querySelector("tbody");
    tbody.innerHTML = "";
    data.items.forEach((item) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${item.rank}</td>
        <td>${item.name}</td>
        <td>${item.score}</td>
        <td>${new Date(item.last_updated).toLocaleString()}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("Failed to load leaderboard:", err);
  }
}

async function loadProfile() {
  if (!currentPlayerId) return;
  try {
    const data = await apiRequest(`/player/${currentPlayerId}`);
    setText("profile-rank", data.rank ?? "-");
    setText("profile-best-score", data.best_score.toString());
    setText(
      "profile-last-updated",
      new Date(data.last_updated).toLocaleString()
    );
  } catch (err) {
    console.error("Failed to load profile:", err);
  }
}

async function loadHistory() {
  if (!currentPlayerId) return;
  try {
    const data = await apiRequest(`/player/${currentPlayerId}/history?limit=10`);
    const list = document.getElementById("history-list");
    list.innerHTML = "";
    data.history.forEach((item) => {
      const li = document.createElement("li");
      li.textContent = `${item.score} points at ${new Date(
        item.created_at
      ).toLocaleString()}`;
      list.appendChild(li);
    });
  } catch (err) {
    console.error("Failed to load history:", err);
  }
}

function refreshPlayerViews() {
  loadLeaderboard();
  loadProfile();
  loadHistory();
}

// Update leaderboard heading to show current N
function updateLeaderboardHeading() {
  const heading = document.getElementById("leaderboard-heading");
  if (heading) {
    heading.textContent = `Top ${leaderboardCount} Leaderboard`;
  }
}

// Initial load - default to Top 10
loadPlayerFromStorage();
updateLeaderboardHeading(); // Set heading to "Top 10 Leaderboard"
loadLeaderboard(); // Load once on page load with default N=10

// Allow user to change Top-N size
const leaderboardInput = document.getElementById("leaderboard-count");
const leaderboardApply = document.getElementById("leaderboard-apply");
if (leaderboardApply && leaderboardInput) {
  leaderboardApply.addEventListener("click", () => {
    const raw = parseInt(leaderboardInput.value, 10);
    if (Number.isNaN(raw)) {
      leaderboardCount = 10;
    } else {
      leaderboardCount = Math.min(100, Math.max(1, raw));
    }
    leaderboardInput.value = leaderboardCount.toString();
    updateLeaderboardHeading(); // Update heading to show new N
    loadLeaderboard(); // Refresh leaderboard with new N
  });
}
