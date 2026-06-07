# 라즈베리파이 배포 (`raspberry-pi` 브랜치)

PC 웹 UI는 Windows에서 `main` 브랜치로 실행하고,  
**책 모드 카메라 + 아두이노 부저** 는 Pi에서 이 브랜치를 clone 해 실행합니다.

## 1. 클론

```bash
git clone -b raspberry-pi https://github.com/phm1204/Smart_Management_System.git
cd Smart_Management_System
```

## 2. 설치 (한 번)

```bash
chmod +x deploy/pi/install.sh
./deploy/pi/install.sh
```

- Python 가상환경 + `requirements-pi.txt` 설치
- `.env` 생성 (아두이노 포트 자동 탐지 시도)
- (선택) systemd 부팅 자동 실행

## 3. 수동 실행

```bash
./deploy/pi/start.sh
```

## 4. PC 연동

Windows PC에서:

```powershell
$env:PI_BASE_URL="http://<Pi-IP>:5001"
python app.py
```

브라우저 → `http://127.0.0.1:5000`  
책 모드 선택 시 Pi 카메라·부저가 연동됩니다.

## 5. 아두이노

`arduino/buzzer/buzzer.ino` 를 업로드 후 USB 연결.

| 핀 | 연결 |
|----|------|
| D8 | 부저(+) |
| D2 | 확인 버튼 |
| GND | 부저(-), 버튼 |

## 6. 환경 변수 (`.env`)

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `BUZZER_SERIAL_PORT` | 아두이노 포트 | `/dev/ttyUSB0` |
| `BUZZER_SERIAL_BAUD` | 시리얼 속도 | `9600` |
| `PI_BUZZER_UDP_PORT` | PC→Pi 부저 UDP | `9999` |
| `PI_SERVICE_PORT` | API 포트 | `5001` |

## 7. 문제 해결

```bash
# API 상태 확인
curl http://localhost:5001/api/status

# 아두이노 포트 확인
ls /dev/ttyUSB* /dev/ttyACM* /dev/serial/by-id/

# 카메라 확인
v4l2-ctl --list-devices

# systemd 로그
sudo journalctl -u smart-focus-pi -f
```
