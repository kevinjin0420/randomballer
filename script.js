const rollButton = document.getElementById("roll");
const resultEl = document.getElementById("result");

let players = null;

async function loadPlayers() {
  if (players) return players;
  const response = await fetch("players.json");
  if (!response.ok) throw new Error(`failed to load players.json (${response.status})`);
  players = await response.json();
  return players;
}

async function rollPlayer() {
  rollButton.disabled = true;
  resultEl.classList.remove("error");
  resultEl.textContent = "Rolling...";
  try {
    const list = await loadPlayers();
    const player = list[Math.floor(Math.random() * list.length)];
    resultEl.innerHTML = "";
    const link = document.createElement("a");
    link.href = `https://www.basketball-reference.com${player.url}`;
    link.textContent = player.name;
    link.target = "_blank";
    link.rel = "noopener";
    resultEl.appendChild(link);
  } catch (err) {
    resultEl.classList.add("error");
    resultEl.textContent = "Couldn't load player list. Try refreshing.";
    console.error(err);
  } finally {
    rollButton.disabled = false;
  }
}

rollButton.addEventListener("click", rollPlayer);
