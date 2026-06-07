/*
 * Smart Focus — 부저 + 확인 버튼
 *
 * 배선:
 *   D8  → 부저(+)
 *   D2  → 버튼 한쪽 (INPUT_PULLUP)
 *   GND → 부저(-), 버튼 다른쪽
 *
 * 시리얼 (9600 baud):
 *   B → 부저 시작 (버튼 누를 때까지 유지)
 *   S → 부저 강제 정지
 *   A ← 버튼 눌러 확인 시 Pi로 전송
 */

const int BUZZER_PIN = 8;
const int BUTTON_PIN = 2;

bool buzzing = false;
unsigned long lastButtonMs = 0;
const unsigned long DEBOUNCE_MS = 300;

void setup() {
  Serial.begin(9600);
  pinMode(BUZZER_PIN, OUTPUT);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  digitalWrite(BUZZER_PIN, LOW);
}

void loop() {
  while (Serial.available() > 0) {
    char cmd = Serial.read();
    if (cmd == 'B') {
      buzzing = true;
    } else if (cmd == 'S') {
      buzzing = false;
    }
  }

  digitalWrite(BUZZER_PIN, buzzing ? HIGH : LOW);

  if (buzzing && digitalRead(BUTTON_PIN) == LOW) {
    unsigned long now = millis();
    if (now - lastButtonMs > DEBOUNCE_MS) {
      buzzing = false;
      Serial.write('A');
      lastButtonMs = now;
    }
  }
}
