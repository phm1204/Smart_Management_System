/**
 * 대시보드 — /api/status 실시간 폴링
 */
async function refreshStatus() {
  const els = {
    focusScore: document.getElementById("focus-score"),
    focusTime: document.getElementById("focus-time"),
    distractTime: document.getElementById("distract-time"),
    activeWindow: document.getElementById("active-window"),
    statusMessage: document.getElementById("status-message"),
    focusState: document.getElementById("focus-state"),
    statusBanner: document.getElementById("status-banner"),
    focusBar: document.getElementById("focus-bar"),
    monitorRunning: document.getElementById("monitor-running"),
  };

  if (!els.focusScore) return;

  try {
    const res = await fetch("/api/status");
    const data = await res.json();

    const score = data.focus_score ?? 0;
    els.focusScore.textContent = `${score}%`;
    els.focusTime.textContent = formatSeconds(data.focus_time_sec);
    els.distractTime.textContent = formatSeconds(data.distract_time_sec);
    els.activeWindow.textContent = data.active_window || "—";

    if (els.focusBar) {
      els.focusBar.style.width = `${Math.min(100, Math.max(0, score))}%`;
    }

    if (els.focusState) {
      els.focusState.textContent = data.focused
        ? "집중 중"
        : "집중 이탈";
    }

    if (els.statusBanner) {
      els.statusBanner.dataset.focused = data.focused ? "true" : "false";
    }

    if (els.statusMessage) {
      els.statusMessage.textContent = data.message || "";
    }

    if (els.monitorRunning) {
      if (data.running) {
        els.monitorRunning.textContent = "실행 중";
        els.monitorRunning.className = "badge badge--live";
      } else {
        els.monitorRunning.textContent = "중지";
        els.monitorRunning.className = "badge badge--idle";
      }
    }
  } catch {
    if (els.statusMessage) {
      els.statusMessage.textContent = "서버 연결 실패";
    }
    if (els.monitorRunning) {
      els.monitorRunning.textContent = "오류";
      els.monitorRunning.className = "badge badge--idle";
    }
  }
}

function formatSeconds(sec) {
  const s = Math.max(0, Number(sec) || 0);
  const m = Math.floor(s / 60);
  const r = s % 60;
  return m > 0 ? `${m}분 ${r}초` : `${r}초`;
}

document.addEventListener("DOMContentLoaded", () => {
  refreshStatus();
  setInterval(refreshStatus, 1000);
});
