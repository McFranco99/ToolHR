const statusEl = document.getElementById("api-status");

const API_BASE_URL = "http://localhost:8000";

async function checkApiHealth() {
  if (!statusEl) return;

  statusEl.textContent = "Connessione...";
  statusEl.className = "pill warning";

  try {
    const response = await fetch(`${API_BASE_URL}/health`);
    if (!response.ok) {
      throw new Error("API non raggiungibile");
    }

    statusEl.textContent = "Online";
    statusEl.className = "pill success";
  } catch (error) {
    statusEl.textContent = "Offline";
    statusEl.className = "pill danger";
  }
}

checkApiHealth();
