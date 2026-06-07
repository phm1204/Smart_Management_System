#!/usr/bin/env bash
# 라즈베리파이 초기 설치 — clone 후 한 번 실행
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "== Smart Focus Pi 설치 =="
echo "경로: $ROOT"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 가 필요합니다."
  exit 1
fi

echo "[1/5] 시스템 패키지 설치..."
sudo apt-get update
sudo apt-get install -y \
  python3 python3-venv python3-pip \
  v4l-utils libcap-dev

echo "[2/5] Python 가상환경..."
python3 -m venv "$ROOT/.venv"
# shellcheck disable=SC1091
source "$ROOT/.venv/bin/activate"
pip install --upgrade pip
pip install -r "$ROOT/requirements-pi.txt"

echo "[3/5] 환경 설정 (.env)..."
if [[ ! -f "$ROOT/.env" ]]; then
  cp "$ROOT/deploy/pi/env.example" "$ROOT/.env"

  SERIAL_PORT=""
  for candidate in /dev/ttyUSB0 /dev/ttyACM0 /dev/serial/by-id/*; do
    if [[ -e "$candidate" ]]; then
      SERIAL_PORT="$candidate"
      break
    fi
  done

  if [[ -n "$SERIAL_PORT" ]]; then
    sed -i "s|^BUZZER_SERIAL_PORT=.*|BUZZER_SERIAL_PORT=${SERIAL_PORT}|" "$ROOT/.env"
    echo "  아두이노 포트 자동 설정: $SERIAL_PORT"
  else
    echo "  아두이노를 찾지 못했습니다. .env 에 BUZZER_SERIAL_PORT 를 직접 설정하세요."
  fi
else
  echo "  기존 .env 유지"
fi

echo "[4/5] 실행 권한..."
chmod +x "$ROOT/deploy/pi/start.sh"

echo "[5/5] systemd 서비스 (선택)..."
read -r -p "부팅 시 자동 실행 systemd 등록? [y/N] " USE_SYSTEMD
if [[ "${USE_SYSTEMD,,}" == "y" ]]; then
  SERVICE_FILE="/etc/systemd/system/smart-focus-pi.service"
  TMP_SERVICE="$(mktemp)"
  sed \
    -e "s|/home/pi/Smart_Management_System|${ROOT}|g" \
    -e "s|^User=pi|User=${USER}|" \
    -e "s|^Group=pi|Group=${USER}|" \
    "$ROOT/deploy/pi/smart-focus-pi.service" > "$TMP_SERVICE"
  sudo cp "$TMP_SERVICE" "$SERVICE_FILE"
  rm -f "$TMP_SERVICE"
  sudo systemctl daemon-reload
  sudo systemctl enable smart-focus-pi.service
  sudo systemctl restart smart-focus-pi.service
  echo "  smart-focus-pi.service 등록 완료"
  echo "  상태 확인: sudo systemctl status smart-focus-pi"
else
  echo "  수동 실행: ./deploy/pi/start.sh"
fi

PI_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
PORT="$(grep '^PI_SERVICE_PORT=' "$ROOT/.env" | cut -d= -f2)"
PORT="${PORT:-5001}"

echo ""
echo "== 설치 완료 =="
echo "Pi API: http://${PI_IP:-<Pi-IP>}:${PORT}"
echo "PC 설정:  PI_BASE_URL=http://${PI_IP:-<Pi-IP>}:${PORT}"
echo ""
echo "테스트: curl http://localhost:${PORT}/api/status"
