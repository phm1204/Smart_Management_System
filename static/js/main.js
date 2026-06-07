/**
 * 대시보드 — /api/status 실시간 폴링 + 측정 제어
 */
let statusInFlight = false;

async function refreshStatus() {
  if (statusInFlight) return;
  statusInFlight = true;
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
    timerStatus: document.getElementById("timer-status"),
    startBtn: document.getElementById("monitor-start"),
    pauseBtn: document.getElementById("monitor-pause"),
    faceDirection: document.getElementById("face-direction-value"),
    gazeDirection: document.getElementById("gaze-direction-value"),
    instantFocusScore: document.getElementById("instant-focus-score"),
    focusFormulaText: document.getElementById("focus-formula-text"),
    buzzerBanner: document.getElementById("buzzer-banner"),
  };

  if (!els.focusScore) return;

  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    const isRunning = Boolean(data.running);

    const score = data.focus_score ?? 0;
    if (isRunning) {
      els.focusScore.textContent = `${score}점`;
      els.focusTime.textContent = formatSeconds(data.focus_time_sec);
      els.distractTime.textContent = formatSeconds(data.distract_time_sec);

      const currentWindow = data.active_window || "—";
      if (els.activeWindow) {
        const previous = els.activeWindow.textContent;
        els.activeWindow.textContent = currentWindow;

        // 활성 창이 바뀔 때만 히스토리에 추가
        if (currentWindow !== "—" && currentWindow !== previous) {
          appendWindowHistory(currentWindow);
        }
      }

      if (els.faceDirection) {
        els.faceDirection.textContent = data.face_direction || "—";
      }
      if (els.gazeDirection) {
        els.gazeDirection.textContent = data.gaze_direction || "—";
      }
      if (els.instantFocusScore) {
        const instant = data.instant_focus_score;
        els.instantFocusScore.textContent =
          instant === undefined || instant === null ? "—" : `${instant}점`;
      }
    } else {
      els.focusScore.textContent = "—";
      els.focusTime.textContent = "—";
      els.distractTime.textContent = "—";
      if (els.activeWindow) {
        els.activeWindow.textContent = "—";
      }
      if (els.faceDirection) {
        els.faceDirection.textContent = "—";
      }
      if (els.gazeDirection) {
        els.gazeDirection.textContent = "—";
      }
      if (els.instantFocusScore) {
        els.instantFocusScore.textContent = "—";
      }
    }

    if (els.focusBar) {
      const barScore = isRunning ? score : 0;
      els.focusBar.style.width = `${Math.min(100, Math.max(0, barScore))}%`;
    }

    if (els.focusState) {
      els.focusState.textContent = isRunning
        ? (data.focused ? "집중 중" : "집중 이탈")
        : "—";
    }

    if (els.statusBanner) {
      els.statusBanner.dataset.focused =
        isRunning && data.focused ? "true" : "false";
    }

    if (els.statusMessage) {
      els.statusMessage.textContent = isRunning ? (data.message || "") : "—";
    }

    if (els.focusFormulaText && data.focus_formula) {
      els.focusFormulaText.textContent = data.focus_formula;
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

    if (els.timerStatus) {
      els.timerStatus.textContent = data.running ? "측정 중" : "시작 대기";
    }
    if (els.startBtn) {
      els.startBtn.disabled = Boolean(data.running);
    }
    if (els.pauseBtn) {
      els.pauseBtn.disabled = !data.running;
    }

    if (els.buzzerBanner) {
      els.buzzerBanner.classList.toggle("hidden", !data.buzzer_active);
    }
  } catch {
    if (els.statusMessage) {
      els.statusMessage.textContent = "서버 연결 실패";
    }
    if (els.monitorRunning) {
      els.monitorRunning.textContent = "오류";
      els.monitorRunning.className = "badge badge--idle";
    }
  } finally {
    statusInFlight = false;
  }
}

function appendWindowHistory(title) {
  const list = document.getElementById("window-history-list");
  if (!list) return;

  const li = document.createElement("li");
  const now = new Date();
  const timeLabel = now.toTimeString().slice(0, 8); // HH:MM:SS
  li.textContent = `[${timeLabel}] ${title}`;

  list.prepend(li);

  // 최근 10개까지만 유지
  while (list.children.length > 10) {
    list.removeChild(list.lastElementChild);
  }
}

function formatSeconds(sec) {
  const s = Math.max(0, Number(sec) || 0);
  const m = Math.floor(s / 60);
  const r = s % 60;
  return m > 0 ? `${m}분 ${r}초` : `${r}초`;
}

async function controlMonitor(action) {
  try {
    await fetch(`/api/monitor/${action}`, { method: "POST" });
    await refreshStatus();
  } catch {
    const timerStatus = document.getElementById("timer-status");
    if (timerStatus) {
      timerStatus.textContent = "요청 실패";
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const startBtn = document.getElementById("monitor-start");
  const pauseBtn = document.getElementById("monitor-pause");
  const resetBtn = document.getElementById("monitor-reset");

  if (startBtn) {
    startBtn.addEventListener("click", () => controlMonitor("start"));
  }
  if (pauseBtn) {
    pauseBtn.addEventListener("click", () => controlMonitor("pause"));
  }
  if (resetBtn) {
    resetBtn.addEventListener("click", () => controlMonitor("reset"));
  }

  const guideOverlay = document.getElementById("camera-guide-overlay");
  const guideCloseBtn = document.getElementById("camera-guide-close");
  if (guideOverlay && guideCloseBtn) {
    const closeGuide = () => guideOverlay.classList.add("hidden");
    guideCloseBtn.addEventListener("click", closeGuide);
    guideOverlay.addEventListener("click", (event) => {
      if (event.target === guideOverlay) closeGuide();
    });
  }

  const learningType = document.getElementById("learning-type-badge")?.textContent?.trim();
  const pollMs = learningType === "book" ? 3000 : 1000;

  const poll = () => {
    if (document.hidden) return;
    refreshStatus();
  };

  refreshStatus();
  setInterval(poll, pollMs);
});
