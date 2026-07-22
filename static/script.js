const alertList = document.getElementById("alert-list");
let lastAlertId = null;

function formatTime(iso) {
  const d = new Date(iso);
  return d.toLocaleString();
}

async function refreshAlerts() {
  try {
    const res = await fetch("/api/alerts");
    const alerts = await res.json();

    alertList.innerHTML = "";
    alerts.forEach(a => {
      const li = document.createElement("li");
      li.innerHTML = `<strong>${a.camera_name}</strong> - abnormal activity detected
                       <span class="time">${formatTime(a.created_at)}</span>`;
      alertList.appendChild(li);
    });

    if (alerts.length && alerts[0].id !== lastAlertId) {
      if (lastAlertId !== null) {
        // A brand-new alert arrived since our last check - flash the tab title
        document.title = "⚠ New Alert! - Hostel CCTV Monitor";
      }
      lastAlertId = alerts[0].id;
    }
  } catch (e) {
    console.error("Failed to fetch alerts", e);
  }
}

async function refreshStatus() {
  try {
    const res = await fetch("/api/camera_status");
    const cameras = await res.json();
    cameras.forEach(c => {
      const dot = document.getElementById(`status-${c.id}`);
      if (dot) {
        dot.classList.toggle("online", c.connected);
        dot.classList.toggle("offline", !c.connected);
      }
    });
  } catch (e) {
    console.error("Failed to fetch camera status", e);
  }
}

document.addEventListener("click", () => {
  document.title = "Hostel CCTV Monitor";
});

refreshAlerts();
refreshStatus();
setInterval(refreshAlerts, 4000);
setInterval(refreshStatus, 5000);
